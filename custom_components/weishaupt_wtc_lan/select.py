"""Select platform for Weishaupt WTC integration.

Exposes writable registers with value maps as dropdowns in Home Assistant.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .heating_circuits import SELECT_SENSOR_KEYS
from .sensor import (
    _device_identifier,
    _device_model,
    _device_name,
    _is_system_device,
)
from .sensors import WeishauptDeviceGroup, WeishauptSensorDefinition

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Weishaupt Select entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[WeishauptSelectEntity] = []

    # Implement writable Betriebart selects for the system and detected circuits.
    for sensor_def in coordinator.sensor_definitions:
        if (
            sensor_def.key in SELECT_SENSOR_KEYS
            or (
                sensor_def.mi == 0x02
                and sensor_def.ox == 0x2533
                and sensor_def.os == 0x02
                and sensor_def.vs == 1
                and sensor_def.value_map
            )
        ):
            entities.append(
                WeishauptSelectEntity(
                    coordinator=coordinator, sensor_def=sensor_def, entry=entry
                )
            )

    async_add_entities(entities)


class WeishauptSelectEntity(CoordinatorEntity, SelectEntity):
    """Representation of a writable Weishaupt value-map as a Select."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        sensor_def: WeishauptSensorDefinition,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_def = sensor_def
        self._entry = entry

        if sensor_def.key in SELECT_SENSOR_KEYS:
            self._attr_unique_id = f"{entry.entry_id}_{sensor_def.key}"
        else:
            self._attr_unique_id = f"{entry.entry_id}_{sensor_def.key}_select"
        self._attr_name = sensor_def.name
        self._attr_icon = sensor_def.icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info so the entity is attached to the correct device."""
        group = self._sensor_def.group
        info = DeviceInfo(
            identifiers={
                _device_identifier(self._entry.entry_id, group, self._sensor_def)
            },
            name=_device_name(self.coordinator, group, self._sensor_def),
            manufacturer="Weishaupt",
            model=_device_model(group, self._sensor_def),
        )
        if not _is_system_device(self._entry.entry_id, group, self._sensor_def):
            info["via_device"] = _device_identifier(
                self._entry.entry_id, WeishauptDeviceGroup.SG
            )
        return info

    @property
    def options(self) -> list[str]:
        """Return available options for the select (ordered by raw value)."""
        if not self._sensor_def.value_map:
            return []
        return [
            self._sensor_def.value_map[k]
            for k in sorted(self._sensor_def.value_map.keys())
        ]

    @property
    def current_option(self) -> str | None:
        """Return currently selected option string, or None if unknown."""
        if self.coordinator.data is None:
            return None

        data = self.coordinator.data.get(self._sensor_def.key)
        if data is None:
            return None

        raw = data.get("value_int")
        if raw is None:
            return None

        option = (self._sensor_def.value_map or {}).get(raw)
        if option is None:
            _LOGGER.debug(
                "Unknown select value for %s: raw_value_int=%s raw_value_hex=%s",
                self._sensor_def.key,
                raw,
                data.get("value_hex", ""),
            )
        return option

    async def async_select_option(self, option: Any) -> None:  # type: ignore[override]
        """Write the chosen option back to the device and refresh data."""
        # Find raw integer matching the selected option
        inv_map = {v: k for k, v in (self._sensor_def.value_map or {}).items()}
        if option not in inv_map:
            _LOGGER.error(
                "Invalid option selected for %s: %s", self._sensor_def.key, option
            )
            return

        raw_value = inv_map[option]

        try:
            success = await self.coordinator.client.write_parameter(
                mi=self._sensor_def.mi,
                mx=self._sensor_def.mx,
                ox=self._sensor_def.ox,
                os_val=self._sensor_def.os,
                vs=self._sensor_def.vs,
                value_int=raw_value,
            )
        except Exception as err:  # catch client errors
            _LOGGER.error(
                "Failed to write %s=%s: %s", self._sensor_def.key, option, err
            )
            return

        if success:
            # Refresh coordinator data to reflect the new state
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.debug("Write reported unsuccessful for %s", self._sensor_def.key)
