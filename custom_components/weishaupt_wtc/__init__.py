"""The Weishaupt WTC integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WeishauptApiClient
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
from .heating_circuits import build_sensor_definitions

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT, Platform.BUTTON]


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
    for circuit_number, mx in ((2, 0x01), (3, 0x02)):
        try:
            if await client.has_heating_circuit(mx):
                active_heating_circuits.append(circuit_number)
        except Exception as err:
            _LOGGER.debug(
                "Heating circuit HK%s probe failed: %s", circuit_number, err
            )

    sensor_definitions = build_sensor_definitions(active_heating_circuits)

    coordinator = WeishauptDataUpdateCoordinator(
        hass=hass,
        client=client,
        scan_interval=scan_interval,
        sensor_definitions=sensor_definitions,
        active_heating_circuits=active_heating_circuits,
        heating_circuit_names=heating_circuit_names,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
