"""The Weishaupt WTC integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .api import ProbeStatus, WeishauptApiClient
from .const import (
    CONF_HK1_NAME,
    CONF_HK2_NAME,
    CONF_HK3_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_HEATING_CIRCUIT_NAMES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import WeishauptDataUpdateCoordinator
from .heating_circuits import (
    DEVICE_GROUP_SOL,
    DEVICE_GROUP_SYSTEM,
    DEVICE_GROUP_WTC,
    DEVICE_GROUP_WW,
    build_sensor_definitions,
    device_groups_from_systable_csv,
    is_plausible_presence_value,
    probe_sensor_definitions_for_group,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
]


async def _async_detect_device_group(
    client: WeishauptApiClient,
    group: str,
    *,
    default_on_unknown: bool,
) -> str:
    """Detect whether a logical device group is present."""
    probe_definitions = probe_sensor_definitions_for_group(group)
    if not probe_definitions:
        return ProbeStatus.PRESENT if default_on_unknown else ProbeStatus.UNKNOWN

    saw_unknown = False
    for sensor_def in probe_definitions:
        status, data = await client.probe_parameter(
            mi=sensor_def.mi,
            mx=sensor_def.mx,
            ox=sensor_def.ox,
            os_val=sensor_def.os,
            vs=sensor_def.vs,
        )
        if status == ProbeStatus.PRESENT and data and is_plausible_presence_value(sensor_def, data):
            _LOGGER.debug("Detected Weishaupt %s via %s", group, sensor_def.key)
            return ProbeStatus.PRESENT
        if status == ProbeStatus.UNKNOWN:
            saw_unknown = True

    if saw_unknown:
        _LOGGER.debug("Presence probe for Weishaupt %s is inconclusive", group)
        return ProbeStatus.PRESENT if default_on_unknown else ProbeStatus.UNKNOWN
    _LOGGER.debug("No plausible presence value found for Weishaupt %s", group)
    return ProbeStatus.ABSENT


async def _async_detect_systable_device_groups(
    client: WeishauptApiClient,
) -> set[str] | None:
    """Use systable.csv as the primary read-only module inventory when present."""
    csv_text = await client.fetch_systable_csv()
    if csv_text is None:
        return None

    groups = device_groups_from_systable_csv(csv_text)
    _LOGGER.debug("Detected Weishaupt groups from systable.csv: %s", sorted(groups))
    return groups


def _systable_status_for_group(systable_groups: set[str] | None, group: str) -> str:
    """Return a primary systable presence decision for a logical group."""
    if systable_groups is None:
        return ProbeStatus.UNKNOWN
    if group in systable_groups:
        return ProbeStatus.PRESENT
    if group == DEVICE_GROUP_SOL:
        return ProbeStatus.ABSENT
    return ProbeStatus.UNKNOWN


async def _async_detect_heating_circuit(
    client: WeishauptApiClient, circuit_number: int, mx: int
) -> str:
    """Detect whether an external heating circuit is present."""
    status, _data = await client.probe_parameter(
        mi=0x02,
        mx=mx,
        ox=0x2533,
        os_val=0x02,
        vs=1,
    )
    if status == ProbeStatus.PRESENT:
        _LOGGER.debug("Detected heating circuit HK%s", circuit_number)
    elif status == ProbeStatus.ABSENT:
        _LOGGER.debug("Heating circuit HK%s is not present", circuit_number)
    else:
        _LOGGER.debug("Heating circuit HK%s probe is inconclusive", circuit_number)
    return status


async def _async_cleanup_inactive_devices(
    hass: HomeAssistant, entry: ConfigEntry, inactive_suffixes: set[str]
) -> None:
    """Remove stale integration-owned entities/devices for inactive groups."""
    if not inactive_suffixes:
        return

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    for suffix in inactive_suffixes:
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"{entry.entry_id}_{suffix}")}
        )
        if device is None:
            continue

        entries = er.async_entries_for_device(entity_registry, device.id)
        if any(entity.config_entry_id != entry.entry_id for entity in entries):
            _LOGGER.debug(
                "Skipping cleanup for %s because foreign entities are attached",
                suffix,
            )
            continue

        for entity in entries:
            entity_registry.async_remove(entity.entity_id)

        if not er.async_entries_for_device(entity_registry, device.id):
            device_registry.async_remove_device(device.id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Weishaupt WTC from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    scan_interval = int(
        entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
    )
    heating_circuit_names = {
        1: entry.options.get(
            CONF_HK1_NAME,
            entry.data.get(CONF_HK1_NAME, DEFAULT_HEATING_CIRCUIT_NAMES[1]),
        ),
        2: entry.options.get(
            CONF_HK2_NAME,
            entry.data.get(CONF_HK2_NAME, DEFAULT_HEATING_CIRCUIT_NAMES[2]),
        ),
        3: entry.options.get(
            CONF_HK3_NAME,
            entry.data.get(CONF_HK3_NAME, DEFAULT_HEATING_CIRCUIT_NAMES[3]),
        ),
    }

    session = async_get_clientsession(hass)
    client = WeishauptApiClient(
        host=host,
        username=username,
        password=password,
        session=session,
    )

    active_heating_circuits = [1]
    inactive_suffixes: set[str] = set()
    for circuit_number, mx in ((2, 0x01), (3, 0x02)):
        status = await _async_detect_heating_circuit(client, circuit_number, mx)
        if status == ProbeStatus.PRESENT:
            active_heating_circuits.append(circuit_number)
        elif status == ProbeStatus.ABSENT:
            inactive_suffixes.add("hk" if circuit_number == 2 else "hk3")

    active_device_groups = {DEVICE_GROUP_SYSTEM}
    systable_groups = await _async_detect_systable_device_groups(client)

    wtc_status = _systable_status_for_group(systable_groups, DEVICE_GROUP_WTC)
    if wtc_status == ProbeStatus.UNKNOWN:
        wtc_status = await _async_detect_device_group(
            client, DEVICE_GROUP_WTC, default_on_unknown=True
        )
    if wtc_status == ProbeStatus.PRESENT:
        active_device_groups.add(DEVICE_GROUP_WTC)
    elif wtc_status == ProbeStatus.ABSENT:
        inactive_suffixes.add("wtc")

    ww_status = _systable_status_for_group(systable_groups, DEVICE_GROUP_WW)
    if ww_status == ProbeStatus.UNKNOWN:
        ww_status = await _async_detect_device_group(
            client, DEVICE_GROUP_WW, default_on_unknown=True
        )
    if ww_status == ProbeStatus.PRESENT:
        active_device_groups.add(DEVICE_GROUP_WW)
    elif ww_status == ProbeStatus.ABSENT:
        inactive_suffixes.add("ww")

    sol_status = _systable_status_for_group(systable_groups, DEVICE_GROUP_SOL)
    if sol_status == ProbeStatus.UNKNOWN:
        sol_status = await _async_detect_device_group(
            client, DEVICE_GROUP_SOL, default_on_unknown=False
        )
    if sol_status == ProbeStatus.PRESENT:
        active_device_groups.add(DEVICE_GROUP_SOL)
    elif sol_status == ProbeStatus.ABSENT:
        inactive_suffixes.add("sol")

    sensor_definitions = build_sensor_definitions(
        active_heating_circuits,
        active_device_groups,
    )

    coordinator = WeishauptDataUpdateCoordinator(
        hass=hass,
        client=client,
        scan_interval=scan_interval,
        sensor_definitions=sensor_definitions,
        active_heating_circuits=active_heating_circuits,
        heating_circuit_names=heating_circuit_names,
        active_device_groups=active_device_groups,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_cleanup_inactive_devices(
        hass,
        entry,
        inactive_suffixes,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
