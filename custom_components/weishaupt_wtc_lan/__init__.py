"""The Weishaupt WTC integration."""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .api import ProbeStatus, WeishauptApiClient
from .const import (
    CONF_DETECTED_HEATING_CIRCUIT_NAMES,
    CONF_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
    CONF_ENABLE_EXPERIMENTAL_WTC_SENSORS,
    CONF_HK1_NAME,
    CONF_HK2_NAME,
    CONF_HK3_NAME,
    CONF_SCAN_INTERVAL,
    CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
    DEFAULT_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
    DEFAULT_ENABLE_EXPERIMENTAL_WTC_SENSORS,
    DEFAULT_HEATING_CIRCUIT_NAMES,
    DEFAULT_USE_DETECTED_HEATING_CIRCUIT_NAMES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EXPERIMENTAL_WTC_DEVICE_SUFFIX,
    NETWORK_DEVICE_SUFFIX,
    SERVICE_EXPORT_EXPERIMENTAL_SNAPSHOT,
    SERVICE_EXPORT_LOCAL_METADATA,
)
from .coordinator import WeishauptDataUpdateCoordinator
from .heating_circuits import (
    DEVICE_GROUP_SOL,
    DEVICE_GROUP_SYSTEM,
    DEVICE_GROUP_WTC,
    DEVICE_GROUP_WW,
    build_sensor_definitions,
    device_groups_from_systable_csv,
    heating_circuit_names_from_config,
    heating_circuit_names_from_systable_csv,
    is_writable_operating_mode_definition,
    is_plausible_presence_value,
    probe_sensor_definitions_for_group,
    resolve_heating_circuit_names,
)
from .sensors import (
    EXPERIMENTAL_WTC_REGISTERS,
    EXTENDED_EXPERIMENTAL_WTC_MAX_ENTITIES,
    EXTENDED_EXPERIMENTAL_WTC_REGISTERS,
    NETWORK_SENSORS,
    ExperimentalWtcRegister,
    WeishauptSensorDefinition,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
]

WTC_POWER_KEY = "wtc_waermeleistung_vpt"
NETWORK_HOSTNAME_KEY = "network_hostname"
DEFAULT_ENABLED_SENSOR_KEYS = {
    "sg_device_date",
    "sg_device_clock_time",
    "network_hostname",
    "network_ip_mode",
    "network_ip_address",
    "network_subnet_mask",
    "network_gateway",
    "network_dns_server",
}
STALE_READONLY_OPERATING_MODE_SENSOR_KEYS = {
    "hk_betriebsart_vorgabe",
    "hk3_betriebsart_vorgabe",
}


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


async def _async_probe_experimental_wtc_registers(
    client: WeishauptApiClient,
    registers: tuple[ExperimentalWtcRegister, ...] = EXPERIMENTAL_WTC_REGISTERS,
) -> list[ExperimentalWtcRegister]:
    """Return curated experimental WTC registers with setup-time responses."""
    params = [
        {
            "key": register.key,
            "mi": register.mi,
            "mx": register.mx,
            "ox": register.ox,
            "os": register.os,
            "vs": register.vs,
        }
        for register in registers
    ]
    results = await client.read_parameters(params)
    supported = [
        register for register in registers if register.key in results
    ]
    _LOGGER.debug(
        "Detected %s supported experimental WTC registers", len(supported)
    )
    return supported


async def _async_probe_wtc_power_definition(
    client: WeishauptApiClient,
    sensor_def: WeishauptSensorDefinition,
) -> WeishauptSensorDefinition:
    """Return the supported value-size definition for WTC VPT power."""
    if sensor_def.key != WTC_POWER_KEY:
        return sensor_def

    for value_size in (4, 2):
        probe_def = replace(sensor_def, vs=value_size)
        results = await client.read_parameters(
            [
                {
                    "key": probe_def.key,
                    "mi": probe_def.mi,
                    "mx": probe_def.mx,
                    "ox": probe_def.ox,
                    "os": probe_def.os,
                    "vs": probe_def.vs,
                }
            ]
        )
        if probe_def.key in results:
            if value_size != sensor_def.vs:
                _LOGGER.debug("Using VS=%s for %s", value_size, sensor_def.key)
            return probe_def

    _LOGGER.debug("No supported value size found for %s", sensor_def.key)
    return replace(sensor_def, poll=False)


async def _async_probe_network_sensors(
    client: WeishauptApiClient,
) -> tuple[list[WeishauptSensorDefinition], dict[str, Any]]:
    """Probe optional read-only network diagnostics."""
    numeric_definitions = [
        sensor_def
        for sensor_def in NETWORK_SENSORS
        if sensor_def.key != NETWORK_HOSTNAME_KEY
    ]
    params = [
        {
            "key": sensor_def.key,
            "mi": sensor_def.mi,
            "mx": sensor_def.mx,
            "ox": sensor_def.ox,
            "os": sensor_def.os,
            "vs": sensor_def.vs,
        }
        for sensor_def in numeric_definitions
    ]
    results = await client.read_parameters(params)
    supported = [sensor_def for sensor_def in numeric_definitions if sensor_def.key in results]
    static_data: dict[str, Any] = {
        sensor_def.key: results[sensor_def.key]
        for sensor_def in supported
    }

    hostname_def = next(
        (sensor_def for sensor_def in NETWORK_SENSORS if sensor_def.key == NETWORK_HOSTNAME_KEY),
        None,
    )
    if hostname_def is not None:
        try:
            hostname_data = await client.read_string_parameter(
                mi=hostname_def.mi,
                mx=hostname_def.mx,
                ox=hostname_def.ox,
                os_val=hostname_def.os,
                vs=hostname_def.vs,
            )
        except AttributeError:
            hostname_data = None
        if hostname_data and str(hostname_data.get("value_string") or "").strip():
            supported.append(hostname_def)
            static_data[NETWORK_HOSTNAME_KEY] = hostname_data

    _LOGGER.debug(
        "Detected supported static network diagnostics: keys=%s",
        sorted(static_data),
    )
    return supported, static_data


def _signed_value(raw_value: int, value_size: int) -> int:
    """Return raw_value interpreted as a signed big-endian integer."""
    sign_bit = 1 << (value_size * 8 - 1)
    full_range = 1 << (value_size * 8)
    if raw_value & sign_bit:
        return raw_value - full_range
    return raw_value


def _integration_version() -> str:
    """Return the integration manifest version."""
    manifest_path = Path(__file__).with_name("manifest.json")
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8")).get(
            "version", "unknown"
        )
    except (OSError, json.JSONDecodeError):
        return "unknown"


def _snapshot_row(
    *,
    key: str,
    address: dict[str, Any],
    data: dict[str, Any] | None,
    source: str,
    hint: str | None = None,
    confidence: str | None = None,
    probable_unit: str | None = None,
    probable_scale: float | None = None,
) -> dict[str, Any]:
    """Build one diagnostic export row without secrets."""
    raw_unsigned = data.get("value_int") if data is not None else None
    value_size = int(address["vs"])
    raw_signed = (
        _signed_value(raw_unsigned, value_size) if raw_unsigned is not None else None
    )
    return {
        "source": source,
        "key": key,
        "mi": f"0x{int(address['mi']):02X}",
        "mx": f"0x{int(address['mx']):02X}",
        "ox": f"0x{int(address['ox']):04X}",
        "os": f"0x{int(address['os']):02X}",
        "vs": value_size,
        "raw_hex": (data or {}).get("value_hex", "").upper(),
        "raw_unsigned": raw_unsigned,
        "raw_signed": raw_signed,
        "scaled_x0_1": round(raw_signed * 0.1, 2) if raw_signed is not None else None,
        "scaled_x0_01": round(raw_signed * 0.01, 2) if raw_signed is not None else None,
        "candidate_hint": hint,
        "confidence": confidence,
        "probable_unit": probable_unit,
        "probable_scale": probable_scale,
    }


def _snapshot_rows(
    coordinator: WeishauptDataUpdateCoordinator,
) -> list[dict[str, Any]]:
    """Collect rows for regular WTC, network, and experimental diagnostics."""
    data = coordinator.data or {}
    rows: list[dict[str, Any]] = []
    for sensor_def in coordinator.sensor_definitions:
        if sensor_def.group.value != DEVICE_GROUP_WTC and not sensor_def.key.startswith(
            "network_"
        ):
            continue
        rows.append(
            _snapshot_row(
                key=sensor_def.key,
                source="regular",
                address={
                    "mi": sensor_def.mi,
                    "mx": sensor_def.mx,
                    "ox": sensor_def.ox,
                    "os": sensor_def.os,
                    "vs": sensor_def.vs,
                },
                data=data.get(sensor_def.key),
                confidence="confirmed" if sensor_def.group.value == DEVICE_GROUP_WTC else "diagnostic",
            )
        )
    for source, registers in (
        ("curated_experimental", coordinator.experimental_wtc_registers),
        ("extended_experimental", coordinator.extended_experimental_wtc_registers),
    ):
        for register in registers:
            rows.append(
                _snapshot_row(
                    key=register.key,
                    source=source,
                    address={
                        "mi": register.mi,
                        "mx": register.mx,
                        "ox": register.ox,
                        "os": register.os,
                        "vs": register.vs,
                    },
                    data=data.get(register.key),
                    hint=register.hint,
                    confidence=register.confidence,
                    probable_unit=register.probable_unit,
                    probable_scale=register.probable_scale,
                )
            )
    return rows


async def _async_export_experimental_snapshot(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: WeishauptDataUpdateCoordinator,
) -> dict[str, str]:
    """Export one read-only diagnostic snapshot to JSON and CSV files."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    rows = _snapshot_rows(coordinator)
    payload = {
        "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
        "integration_version": _integration_version(),
        "host_identifier": entry.data.get(CONF_HOST, ""),
        "entry_id": entry.entry_id,
        "values": rows,
    }

    base_dir = hass.config.path("weishaupt_wtc_lan_diagnostics")
    os.makedirs(base_dir, exist_ok=True)
    json_path = os.path.join(base_dir, f"{timestamp}-experimental-snapshot.json")
    csv_path = os.path.join(base_dir, f"{timestamp}-experimental-snapshot.csv")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(payload, json_file, indent=2, sort_keys=True)
    fieldnames = list(rows[0]) if rows else list(_snapshot_row(
        key="",
        source="",
        address={"mi": 0, "mx": 0, "ox": 0, "os": 0, "vs": 1},
        data=None,
    ))
    with open(csv_path, "w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return {"json_path": json_path, "csv_path": csv_path}


async def _async_export_local_metadata(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: WeishauptDataUpdateCoordinator,
) -> dict[str, str]:
    """Export read-only local metadata used for name detection."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base_dir = hass.config.path(
        "weishaupt_wtc_lan_diagnostics",
        "local_metadata",
    )
    os.makedirs(base_dir, exist_ok=True)

    systable_csv = await coordinator.client.fetch_systable_csv()
    parsed_names = heating_circuit_names_from_systable_csv(systable_csv)
    persisted_names = heating_circuit_names_from_config(
        entry.data.get(CONF_DETECTED_HEATING_CIRCUIT_NAMES, {})
    )
    use_detected_names = bool(
        entry.options.get(
            CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
            entry.data.get(
                CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
                DEFAULT_USE_DETECTED_HEATING_CIRCUIT_NAMES,
            ),
        )
    )
    overrides = {
        1: entry.options.get(CONF_HK1_NAME, entry.data.get(CONF_HK1_NAME, "")),
        2: entry.options.get(CONF_HK2_NAME, entry.data.get(CONF_HK2_NAME, "")),
        3: entry.options.get(CONF_HK3_NAME, entry.data.get(CONF_HK3_NAME, "")),
    }
    detected_for_resolution = parsed_names or persisted_names
    resolved_names = resolve_heating_circuit_names(
        overrides,
        detected_for_resolution,
        use_detected_names,
        DEFAULT_HEATING_CIRCUIT_NAMES,
    )

    written: dict[str, str] = {}
    if systable_csv is not None:
        csv_path = os.path.join(base_dir, f"{timestamp}-systable.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as csv_file:
            csv_file.write(systable_csv)
        written["systable_csv_path"] = csv_path

    summary_path = os.path.join(
        base_dir,
        f"{timestamp}-detected-heating-circuit-names.json",
    )
    summary = {
        "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
        "integration_version": _integration_version(),
        "host_identifier": entry.data.get(CONF_HOST, ""),
        "parser_source": "systable.csv" if systable_csv is not None else "persisted",
        "systable_available": systable_csv is not None,
        "systable_character_length": len(systable_csv) if systable_csv is not None else 0,
        "parsed_heating_circuit_names": {
            str(key): value for key, value in parsed_names.items()
        },
        "persisted_heating_circuit_names": {
            str(key): value for key, value in persisted_names.items()
        },
        "use_detected_heating_circuit_names": use_detected_names,
        "resolved_heating_circuit_names": {
            str(key): value for key, value in resolved_names.items()
        },
    }
    with open(summary_path, "w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2, sort_keys=True, ensure_ascii=False)
    written["summary_json_path"] = summary_path
    return written


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_services_registered"):
        return

    def _entry_and_coordinator(entry_id: str | None) -> tuple[ConfigEntry | None, WeishauptDataUpdateCoordinator | None]:
        coordinators = {
            key: value
            for key, value in hass.data.get(DOMAIN, {}).items()
            if isinstance(value, WeishauptDataUpdateCoordinator)
        }
        if entry_id is None:
            entry_id = next(iter(coordinators), None)
        if entry_id is None:
            return None, None
        coordinator = coordinators.get(entry_id)
        entry = hass.config_entries.async_get_entry(entry_id)
        return entry, coordinator

    async def _handle_snapshot_export(call) -> None:
        entry_id = call.data.get("entry_id") if hasattr(call, "data") else None
        entry, coordinator = _entry_and_coordinator(entry_id)
        if entry is None or coordinator is None:
            _LOGGER.warning("No Weishaupt coordinator available for snapshot export")
            return
        paths = await _async_export_experimental_snapshot(hass, entry, coordinator)
        _LOGGER.info("Exported Weishaupt experimental snapshot: %s", paths)

    async def _handle_local_metadata_export(call) -> None:
        entry_id = call.data.get("entry_id") if hasattr(call, "data") else None
        entry, coordinator = _entry_and_coordinator(entry_id)
        if entry is None or coordinator is None:
            _LOGGER.warning("No Weishaupt coordinator available for metadata export")
            return
        paths = await _async_export_local_metadata(hass, entry, coordinator)
        _LOGGER.info("Exported Weishaupt local metadata: %s", paths)

    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_EXPERIMENTAL_SNAPSHOT,
        _handle_snapshot_export,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_LOCAL_METADATA,
        _handle_local_metadata_export,
    )
    domain_data["_services_registered"] = True


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


def _entity_registry_entry_is_integration_disabled(entry: Any) -> bool:
    """Return True when an entity was disabled by the integration default."""
    disabled_by = getattr(entry, "disabled_by", None)
    integration_disabled = getattr(
        getattr(er, "RegistryEntryDisabler", None),
        "INTEGRATION",
        "integration",
    )
    return disabled_by in ("integration", integration_disabled)


def _entity_id_for_unique_id(entity_registry: Any, domain: str, unique_id: str) -> str | None:
    """Find an entity_id for a unique_id across real and test registries."""
    get_entity_id = getattr(entity_registry, "async_get_entity_id", None)
    if get_entity_id is not None:
        entity_id = get_entity_id(domain, DOMAIN, unique_id)
        if entity_id is not None:
            return entity_id
    entries = getattr(entity_registry, "entries", [])
    for entry in entries:
        if getattr(entry, "domain", domain) == domain and getattr(entry, "unique_id", None) == unique_id:
            return getattr(entry, "entity_id", None)
    return None


def _entity_registry_entry(entity_registry: Any, entity_id: str) -> Any:
    """Return a registry entry from real and test registries."""
    async_get = getattr(entity_registry, "async_get", None)
    if async_get is not None:
        return async_get(entity_id)
    for entry in getattr(entity_registry, "entries", []):
        if getattr(entry, "entity_id", None) == entity_id:
            return entry
    return None


async def _async_reenable_integration_default_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    keys: set[str],
) -> None:
    """Re-enable selected entities only when disabled by integration default."""
    entity_registry = er.async_get(hass)
    for key in keys:
        entity_id = _entity_id_for_unique_id(
            entity_registry,
            "sensor",
            f"{entry.entry_id}_{key}",
        )
        if entity_id is None:
            continue
        entry_obj = _entity_registry_entry(entity_registry, entity_id)
        if entry_obj is None:
            continue
        if getattr(entry_obj, "config_entry_id", entry.entry_id) != entry.entry_id:
            continue
        if not _entity_registry_entry_is_integration_disabled(entry_obj):
            continue
        update_entity = getattr(entity_registry, "async_update_entity", None)
        if update_entity is not None:
            update_entity(entity_id, disabled_by=None)
        elif hasattr(entry_obj, "disabled_by"):
            entry_obj.disabled_by = None


async def _async_cleanup_stale_readonly_operating_mode_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove stale read-only HK2/HK3 operating-mode target sensor entities."""
    entity_registry = er.async_get(hass)
    for key in STALE_READONLY_OPERATING_MODE_SENSOR_KEYS:
        entity_id = _entity_id_for_unique_id(
            entity_registry,
            "sensor",
            f"{entry.entry_id}_{key}",
        )
        if entity_id is None:
            continue
        entry_obj = _entity_registry_entry(entity_registry, entity_id)
        if entry_obj is not None and getattr(entry_obj, "config_entry_id", entry.entry_id) != entry.entry_id:
            continue
        _LOGGER.debug("Removing stale read-only operating-mode sensor %s", entity_id)
        entity_registry.async_remove(entity_id)


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
    enable_experimental_wtc_sensors = bool(
        entry.options.get(
            CONF_ENABLE_EXPERIMENTAL_WTC_SENSORS,
            entry.data.get(
                CONF_ENABLE_EXPERIMENTAL_WTC_SENSORS,
                DEFAULT_ENABLE_EXPERIMENTAL_WTC_SENSORS,
            ),
        )
    )
    enable_extended_experimental_wtc_sensors = bool(
        entry.options.get(
            CONF_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
            entry.data.get(
                CONF_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
                DEFAULT_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
            ),
        )
    )
    use_detected_heating_circuit_names = bool(
        entry.options.get(
            CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
            entry.data.get(
                CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
                DEFAULT_USE_DETECTED_HEATING_CIRCUIT_NAMES,
            ),
        )
    )
    explicit_heating_circuit_names = {
        1: entry.options.get(
            CONF_HK1_NAME,
            entry.data.get(CONF_HK1_NAME, ""),
        ),
        2: entry.options.get(
            CONF_HK2_NAME,
            entry.data.get(CONF_HK2_NAME, ""),
        ),
        3: entry.options.get(
            CONF_HK3_NAME,
            entry.data.get(CONF_HK3_NAME, ""),
        ),
    }

    session = async_get_clientsession(hass)
    client = WeishauptApiClient(
        host=host,
        username=username,
        password=password,
        session=session,
    )

    systable_csv = await client.fetch_systable_csv()
    _LOGGER.debug(
        "systable.csv fetch during setup: available=%s chars=%s",
        systable_csv is not None,
        len(systable_csv) if systable_csv is not None else 0,
    )
    systable_groups = (
        device_groups_from_systable_csv(systable_csv)
        if systable_csv is not None
        else None
    )
    persisted_heating_circuit_names = heating_circuit_names_from_config(
        entry.data.get(CONF_DETECTED_HEATING_CIRCUIT_NAMES, {})
    )
    detected_heating_circuit_names = (
        heating_circuit_names_from_systable_csv(systable_csv)
        if systable_csv is not None
        else persisted_heating_circuit_names
    )
    heating_circuit_names = resolve_heating_circuit_names(
        explicit_heating_circuit_names,
        detected_heating_circuit_names,
        use_detected_heating_circuit_names,
        DEFAULT_HEATING_CIRCUIT_NAMES,
    )
    _LOGGER.debug(
        "Heating-circuit name detection: persisted=%s detected=%s resolved=%s",
        persisted_heating_circuit_names,
        detected_heating_circuit_names,
        heating_circuit_names,
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

    experimental_wtc_registers: list[ExperimentalWtcRegister] = []
    extended_experimental_wtc_registers: list[ExperimentalWtcRegister] = []
    if enable_experimental_wtc_sensors and DEVICE_GROUP_WTC in active_device_groups:
        experimental_wtc_registers = await _async_probe_experimental_wtc_registers(
            client
        )
        if enable_extended_experimental_wtc_sensors:
            extended_catalog = EXTENDED_EXPERIMENTAL_WTC_REGISTERS[
                :EXTENDED_EXPERIMENTAL_WTC_MAX_ENTITIES
            ]
            extended_experimental_wtc_registers = (
                await _async_probe_experimental_wtc_registers(
                    client,
                    extended_catalog,
                )
            )
        if not experimental_wtc_registers and not extended_experimental_wtc_registers:
            inactive_suffixes.add(EXPERIMENTAL_WTC_DEVICE_SUFFIX)
    else:
        inactive_suffixes.add(EXPERIMENTAL_WTC_DEVICE_SUFFIX)

    sensor_definitions = build_sensor_definitions(
        active_heating_circuits,
        active_device_groups,
    )
    sensor_definitions = [
        await _async_probe_wtc_power_definition(client, sensor_def)
        for sensor_def in sensor_definitions
    ]
    network_sensor_definitions, static_data = await _async_probe_network_sensors(client)
    if network_sensor_definitions:
        sensor_definitions.extend(network_sensor_definitions)
    else:
        inactive_suffixes.add(NETWORK_DEVICE_SUFFIX)

    coordinator = WeishauptDataUpdateCoordinator(
        hass=hass,
        client=client,
        scan_interval=scan_interval,
        sensor_definitions=sensor_definitions,
        active_heating_circuits=active_heating_circuits,
        heating_circuit_names=heating_circuit_names,
        active_device_groups=active_device_groups,
        experimental_wtc_registers=experimental_wtc_registers,
        extended_experimental_wtc_registers=extended_experimental_wtc_registers,
        static_data=static_data,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await _async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_cleanup_inactive_devices(
        hass,
        entry,
        inactive_suffixes,
    )
    await _async_cleanup_stale_readonly_operating_mode_sensors(hass, entry)
    await _async_reenable_integration_default_entities(
        hass,
        entry,
        DEFAULT_ENABLED_SENSOR_KEYS,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
