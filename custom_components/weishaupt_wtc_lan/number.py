"""Number platform for Weishaupt WTC integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .heating_circuits import NUMBER_SENSOR_KEYS
from .sensor import (
    _device_identifier,
    _device_model,
    _device_name,
    _is_system_device,
)
from .sensors import WeishauptDeviceGroup, WeishauptSensorDefinition

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeishauptNumberSettings:
    """Number entity settings for a writable sensor definition."""

    min_value: float
    max_value: float
    step: float


NUMBER_SETTINGS = {
    "sg_wwsolltemperatur_normal": WeishauptNumberSettings(50.0, 60.0, 1.0),
    "sg_wwsolltemperatur_absenk": WeishauptNumberSettings(8.0, 60.0, 1.0),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Weishaupt Number entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[WeishauptNumberEntity] = []
    for sensor_def in coordinator.sensor_definitions:
        if sensor_def.key in NUMBER_SENSOR_KEYS:
            entities.append(
                WeishauptNumberEntity(
                    coordinator=coordinator,
                    sensor_def=sensor_def,
                    entry=entry,
                    settings=NUMBER_SETTINGS[sensor_def.key],
                )
            )

    async_add_entities(entities)


class WeishauptNumberEntity(CoordinatorEntity, NumberEntity):
    """Representation of a writable Weishaupt numeric register."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator,
        sensor_def: WeishauptSensorDefinition,
        entry: ConfigEntry,
        settings: WeishauptNumberSettings,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._sensor_def = sensor_def
        self._entry = entry
        self._settings = settings

        self._attr_unique_id = f"{entry.entry_id}_{sensor_def.key}_number"
        self._attr_name = sensor_def.name
        self._attr_icon = sensor_def.icon
        self._attr_native_min_value = settings.min_value
        self._attr_native_max_value = settings.max_value
        self._attr_native_step = settings.step

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info so the entity is attached to warm water."""
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
    def available(self) -> bool:
        """Return True if the current value is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._sensor_def.key in self.coordinator.data
        )

    @property
    def native_value(self) -> float | None:
        """Return the current Celsius value."""
        if self.coordinator.data is None:
            return None

        data = self.coordinator.data.get(self._sensor_def.key)
        if data is None:
            return None

        raw_value = data.get("value_int")
        if raw_value is None or raw_value in (0x8000, 0xFFFF):
            return None

        return round(raw_value * 0.1, 1)

    async def async_set_native_value(self, value: float) -> None:
        """Write a Celsius value to the device."""
        if value < self._settings.min_value or value > self._settings.max_value:
            raise ValueError(
                f"{self._sensor_def.key} must be between "
                f"{self._settings.min_value} and {self._settings.max_value}"
            )

        raw_value = int(round(value * 10))

        try:
            success = await self.coordinator.client.write_parameter(
                mi=self._sensor_def.mi,
                mx=self._sensor_def.mx,
                ox=self._sensor_def.ox,
                os_val=self._sensor_def.os,
                vs=self._sensor_def.vs,
                value_int=raw_value,
            )
        except Exception as err:
            _LOGGER.error("Failed to write %s=%s: %s", self._sensor_def.key, value, err)
            return

        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.debug("Write reported unsuccessful for %s", self._sensor_def.key)
