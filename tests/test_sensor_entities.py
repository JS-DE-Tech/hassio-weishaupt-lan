"""Regression tests for regular and experimental sensor entities."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "custom_components" / "weishaupt_wtc_lan"


def load_module(module_name: str, file_path: Path):
    """Load a package module from a file."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


homeassistant_pkg = types.ModuleType("homeassistant")
homeassistant_pkg.__path__ = []
sys.modules.setdefault("homeassistant", homeassistant_pkg)

components_pkg = types.ModuleType("homeassistant.components")
components_pkg.__path__ = []
sys.modules.setdefault("homeassistant.components", components_pkg)

sensor_component = types.ModuleType("homeassistant.components.sensor")


class SensorEntity:
    """Minimal sensor entity stub."""


class SensorDeviceClass:
    """Return enum member names as strings."""

    def __getattr__(self, name: str) -> str:
        return name


class SensorStateClass:
    """Return enum member names as strings."""

    def __getattr__(self, name: str) -> str:
        return name


sensor_component.SensorEntity = SensorEntity
sensor_component.SensorDeviceClass = SensorDeviceClass()
sensor_component.SensorStateClass = SensorStateClass()
sys.modules["homeassistant.components.sensor"] = sensor_component

config_entries = types.ModuleType("homeassistant.config_entries")
config_entries.ConfigEntry = object
sys.modules["homeassistant.config_entries"] = config_entries

core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
core.callback = lambda func: func
sys.modules["homeassistant.core"] = core

const = types.ModuleType("homeassistant.const")
const.PERCENTAGE = "%"
const.UnitOfEnergy = SimpleNamespace(KILO_WATT_HOUR="kWh")
const.UnitOfPower = SimpleNamespace(KILO_WATT="kW")
const.UnitOfPressure = SimpleNamespace(BAR="bar")
const.UnitOfTemperature = SimpleNamespace(CELSIUS="C")
const.UnitOfTime = SimpleNamespace(HOURS="h")
sys.modules["homeassistant.const"] = const

helpers_pkg = types.ModuleType("homeassistant.helpers")
helpers_pkg.__path__ = []
sys.modules["homeassistant.helpers"] = helpers_pkg

device_registry_module = types.ModuleType("homeassistant.helpers.device_registry")
device_registry_module.DeviceInfo = dict
sys.modules["homeassistant.helpers.device_registry"] = device_registry_module
helpers_pkg.device_registry = device_registry_module

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
entity_platform.AddEntitiesCallback = object
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

entity_module = types.ModuleType("homeassistant.helpers.entity")
entity_module.EntityCategory = SimpleNamespace(DIAGNOSTIC="diagnostic", CONFIG="config")
sys.modules["homeassistant.helpers.entity"] = entity_module

update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")


class CoordinatorEntity:
    """Minimal coordinator entity stub."""

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator

    @property
    def available(self) -> bool:
        return True


update_coordinator.CoordinatorEntity = CoordinatorEntity
sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

custom_components_pkg = types.ModuleType("custom_components")
custom_components_pkg.__path__ = [str(REPO_ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components_pkg)

integration_pkg = types.ModuleType("custom_components.weishaupt_wtc_lan")
integration_pkg.__path__ = [str(PACKAGE_ROOT)]
sys.modules.setdefault("custom_components.weishaupt_wtc_lan", integration_pkg)

load_module("custom_components.weishaupt_wtc_lan.const", PACKAGE_ROOT / "const.py")
load_module("custom_components.weishaupt_wtc_lan.parsing", PACKAGE_ROOT / "parsing.py")
sensors = load_module(
    "custom_components.weishaupt_wtc_lan.sensors", PACKAGE_ROOT / "sensors.py"
)
heating_circuits = load_module(
    "custom_components.weishaupt_wtc_lan.heating_circuits",
    PACKAGE_ROOT / "heating_circuits.py",
)

coordinator_module = types.ModuleType("custom_components.weishaupt_wtc_lan.coordinator")
coordinator_module.WeishauptDataUpdateCoordinator = object
sys.modules["custom_components.weishaupt_wtc_lan.coordinator"] = coordinator_module

sensor = load_module(
    "custom_components.weishaupt_wtc_lan.sensor", PACKAGE_ROOT / "sensor.py"
)


def sensor_by_key(key: str):
    """Return a sensor definition by key."""
    return next(sensor_def for sensor_def in sensors.ALL_SENSORS if sensor_def.key == key)


class DeviceRegistry:
    """Minimal device registry capturing created devices."""

    def __init__(self) -> None:
        self.created: list[dict] = []

    def async_get_or_create(self, **kwargs):
        self.created.append(kwargs)
        return kwargs


class SensorEntityTests(unittest.IsolatedAsyncioTestCase):
    """Test regular and experimental sensor behavior."""

    def test_confirmed_wtc_frames_render_valid_zero_and_counter_values(self) -> None:
        """Confirmed WTC raw values should render expected HA states."""
        keys_and_expected = {
            "wtc_anlagendruck": (149, "0095", 1.49),
            "wtc_kesseltemperatur": (402, "0192", 40.2),
            "wtc_volumenstrom_vpt": (0, "0000", 0),
            "wtc_abgastemperatur": (399, "018f", 39.9),
            "wtc_ruecklauftemperatur": (413, "019d", 41.3),
            "wtc_vorlaufsolltemperatur": (80, "0050", 8.0),
            "wtc_brennerstarts_gesamt": (31261, "7a1d", 31261),
            "wtc_betriebsstunden_gesamt": (5604, "15e4", 5604),
        }
        coordinator = SimpleNamespace(
            data={
                key: {"value_int": raw, "value_hex": raw_hex}
                for key, (raw, raw_hex, _expected) in keys_and_expected.items()
            },
        )
        entry = SimpleNamespace(entry_id="entry-123")

        for key, (_raw, _raw_hex, expected) in keys_and_expected.items():
            entity = sensor.WeishauptSensorEntity(
                coordinator=coordinator,
                sensor_def=sensor_by_key(key),
                entry=entry,
            )
            self.assertTrue(entity.available)
            self.assertEqual(entity.native_value, expected)

    def test_experimental_entity_uses_own_device_and_metadata(self) -> None:
        """Experimental sensors should expose raw signed state and metadata."""
        register = next(
            item
            for item in sensors.EXPERIMENTAL_WTC_REGISTERS
            if item.key == "wtc_experimental_09_01_2612_02_02"
        )
        coordinator = SimpleNamespace(
            data={register.key: {"value_int": 597, "value_hex": "0255"}},
        )
        entity = sensor.WeishauptExperimentalWtcSensorEntity(
            coordinator=coordinator,
            register=register,
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertTrue(entity.available)
        self.assertEqual(entity._attr_unique_id, "entry-123_" + register.key)
        self.assertEqual(entity.native_value, 597)
        self.assertEqual(
            entity.device_info["identifiers"],
            {("weishaupt_wtc_lan", "entry-123_wtc_experimental")},
        )
        attrs = entity.extra_state_attributes
        self.assertEqual(attrs["raw_hex"], "0255")
        self.assertEqual(attrs["raw_unsigned"], 597)
        self.assertEqual(attrs["raw_signed"], 597)
        self.assertEqual(attrs["scaled_x0_1"], 59.7)
        self.assertEqual(attrs["scaled_x0_01"], 5.97)
        self.assertEqual(attrs["mi"], "0x09")
        self.assertEqual(attrs["ox"], "0x2612")
        self.assertEqual(attrs["confidence"], "experimental")

    def test_experimental_zero_is_valid_and_sentinel_is_unavailable(self) -> None:
        """Raw zero should remain valid while sentinel values are unavailable."""
        zero_register = next(
            item
            for item in sensors.EXPERIMENTAL_WTC_REGISTERS
            if item.key == "wtc_experimental_09_01_2619_02_01"
        )
        coordinator = SimpleNamespace(
            data={zero_register.key: {"value_int": 0, "value_hex": "00"}},
        )
        entity = sensor.WeishauptExperimentalWtcSensorEntity(
            coordinator=coordinator,
            register=zero_register,
            entry=SimpleNamespace(entry_id="entry-123"),
        )
        self.assertTrue(entity.available)
        self.assertEqual(entity.native_value, 0)

        sentinel_register = next(
            item
            for item in sensors.EXPERIMENTAL_WTC_REGISTERS
            if item.key == "wtc_experimental_09_01_2612_02_02"
        )
        coordinator.data = {
            sentinel_register.key: {"value_int": 0x8000, "value_hex": "8000"}
        }
        sentinel_entity = sensor.WeishauptExperimentalWtcSensorEntity(
            coordinator=coordinator,
            register=sentinel_register,
            entry=SimpleNamespace(entry_id="entry-123"),
        )
        self.assertFalse(sentinel_entity.available)
        self.assertIsNone(sentinel_entity.native_value)

    async def test_async_setup_entry_adds_no_experimental_entities_when_disabled(self) -> None:
        """An empty experimental register list should not add entities or device."""
        registry = DeviceRegistry()
        sensor.dr.async_get = lambda hass: registry
        added: list = []
        coordinator = SimpleNamespace(
            sensor_definitions=[],
            experimental_wtc_registers=[],
        )
        hass = SimpleNamespace(data={"weishaupt_wtc_lan": {"entry-123": coordinator}})

        await sensor.async_setup_entry(
            hass,
            SimpleNamespace(entry_id="entry-123"),
            lambda entities: added.extend(entities),
        )

        self.assertEqual(added, [])
        self.assertEqual(len(registry.created), 1)


if __name__ == "__main__":
    unittest.main()
