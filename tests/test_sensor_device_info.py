"""Regression tests for Weishaupt device registry metadata."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "custom_components" / "weishaupt_wtc"


def load_module(module_name: str, file_path: Path):
    """Load a module from file while preserving package-relative imports."""
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
    """Return the requested enum member name as a string."""

    def __getattr__(self, name: str) -> str:
        return name


class SensorStateClass:
    """Return the requested enum member name as a string."""

    def __getattr__(self, name: str) -> str:
        return name


sensor_component.SensorEntity = SensorEntity
sensor_component.SensorDeviceClass = SensorDeviceClass()
sensor_component.SensorStateClass = SensorStateClass()
sys.modules.setdefault("homeassistant.components.sensor", sensor_component)

select_component = types.ModuleType("homeassistant.components.select")


class SelectEntity:
    """Minimal select entity stub."""


select_component.SelectEntity = SelectEntity
sys.modules.setdefault("homeassistant.components.select", select_component)

config_entries = types.ModuleType("homeassistant.config_entries")


class ConfigEntry:
    """Minimal config entry stub."""


config_entries.ConfigEntry = ConfigEntry
sys.modules.setdefault("homeassistant.config_entries", config_entries)

core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
core.callback = lambda func: func
sys.modules.setdefault("homeassistant.core", core)

const = types.ModuleType("homeassistant.const")
const.PERCENTAGE = "%"
const.UnitOfEnergy = SimpleNamespace(KILO_WATT_HOUR="kWh")
const.UnitOfPower = SimpleNamespace(KILO_WATT="kW")
const.UnitOfPressure = SimpleNamespace(BAR="bar")
const.UnitOfTemperature = SimpleNamespace(CELSIUS="°C")
const.UnitOfTime = SimpleNamespace(HOURS="h")
sys.modules.setdefault("homeassistant.const", const)

helpers_pkg = types.ModuleType("homeassistant.helpers")
helpers_pkg.__path__ = []
sys.modules.setdefault("homeassistant.helpers", helpers_pkg)

device_registry_module = types.ModuleType("homeassistant.helpers.device_registry")
device_registry_module.DeviceInfo = dict
device_registry_module.async_get = lambda hass: None
helpers_pkg.device_registry = device_registry_module
sys.modules["homeassistant.helpers.device_registry"] = device_registry_module

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
entity_platform.AddEntitiesCallback = object
sys.modules.setdefault("homeassistant.helpers.entity_platform", entity_platform)

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


class DataUpdateCoordinator:
    """Minimal data update coordinator stub."""

    def __class_getitem__(cls, item):
        return cls


class UpdateFailed(Exception):
    """Minimal update failure stub."""


update_coordinator.CoordinatorEntity = CoordinatorEntity
update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
update_coordinator.UpdateFailed = UpdateFailed
sys.modules.setdefault("homeassistant.helpers.update_coordinator", update_coordinator)

custom_components_pkg = types.ModuleType("custom_components")
custom_components_pkg.__path__ = [str(REPO_ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components_pkg)

integration_pkg = types.ModuleType("custom_components.weishaupt_wtc")
integration_pkg.__path__ = [str(PACKAGE_ROOT)]
sys.modules.setdefault("custom_components.weishaupt_wtc", integration_pkg)

load_module("custom_components.weishaupt_wtc.const", PACKAGE_ROOT / "const.py")
load_module("custom_components.weishaupt_wtc.parsing", PACKAGE_ROOT / "parsing.py")
sensors = load_module(
    "custom_components.weishaupt_wtc.sensors", PACKAGE_ROOT / "sensors.py"
)
heating_circuits = load_module(
    "custom_components.weishaupt_wtc.heating_circuits",
    PACKAGE_ROOT / "heating_circuits.py",
)

coordinator_module = types.ModuleType("custom_components.weishaupt_wtc.coordinator")


class WeishauptDataUpdateCoordinator:
    """Minimal coordinator type stub used by the sensor module."""


coordinator_module.WeishauptDataUpdateCoordinator = WeishauptDataUpdateCoordinator
sys.modules["custom_components.weishaupt_wtc.coordinator"] = coordinator_module

sensor = load_module(
    "custom_components.weishaupt_wtc.sensor", PACKAGE_ROOT / "sensor.py"
)
select = load_module(
    "custom_components.weishaupt_wtc.select", PACKAGE_ROOT / "select.py"
)


class SensorDeviceInfoTests(unittest.TestCase):
    """Test device registry metadata for sensor entities."""

    def test_system_device_has_no_via_device(self) -> None:
        """The SG device is the root of the device tree."""
        entity = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(data={}),
            sensor_def=sensors.SG_SENSORS[0],
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(
            entity.device_info["identifiers"],
            {("weishaupt_wtc", "entry-123_sg")},
        )
        self.assertNotIn("via_device", entity.device_info)

    def test_child_device_points_to_system_device(self) -> None:
        """Non-SG groups should reference the SG device as their parent."""
        entity = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(data={}),
            sensor_def=sensors.WTC_SENSORS[0],
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(
            entity.device_info["identifiers"],
            {("weishaupt_wtc", "entry-123_wtc")},
        )
        self.assertEqual(
            entity.device_info["via_device"],
            ("weishaupt_wtc", "entry-123_sg"),
        )

    def test_hk2_keeps_legacy_keys_and_device_identifier(self) -> None:
        """HK2 should keep the historical generic hk_* unique IDs."""
        hk2_defs = heating_circuits.build_hk_sensor_definitions(2, 0x01)
        betriebsart = hk2_defs[0]
        entity = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(
                data={}, heating_circuit_names={2: "Heizkoerper Keller"}
            ),
            sensor_def=betriebsart,
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(betriebsart.key, "hk_betriebsart_vorgabe")
        self.assertEqual(betriebsart.mx, 0x01)
        self.assertEqual(betriebsart.modbus_reg, "1030")
        self.assertEqual(entity._attr_unique_id, "entry-123_hk_betriebsart_vorgabe")
        self.assertEqual(
            entity.device_info["identifiers"],
            {("weishaupt_wtc", "entry-123_hk")},
        )
        self.assertEqual(entity.device_info["name"], "Heizkoerper Keller")

    def test_hk3_gets_numbered_keys_and_device_identifier(self) -> None:
        """HK3 should use MX=0x02 and its own device identifier."""
        hk3_defs = heating_circuits.build_hk_sensor_definitions(3, 0x02)
        betriebsart = hk3_defs[0]
        vorlauf = next(
            sensor_def
            for sensor_def in hk3_defs
            if sensor_def.key == "hk3_vorlaufisttemperatur"
        )
        entity = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(
                data={}, heating_circuit_names={3: "Fussbodenheizung OG"}
            ),
            sensor_def=betriebsart,
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(betriebsart.key, "hk3_betriebsart_vorgabe")
        self.assertEqual(betriebsart.mx, 0x02)
        self.assertEqual(betriebsart.modbus_reg, "1060")
        self.assertEqual(vorlauf.modbus_reg, "1076")
        self.assertEqual(
            entity.device_info["identifiers"],
            {("weishaupt_wtc", "entry-123_hk3")},
        )
        self.assertEqual(entity.device_info["name"], "Fussbodenheizung OG")

    def test_sensor_definitions_exclude_undetected_external_circuits(self) -> None:
        """Only detected external circuits should contribute sensor definitions."""
        hk2_only = heating_circuits.build_sensor_definitions([1, 2])
        hk2_hk3 = heating_circuits.build_sensor_definitions([1, 2, 3])
        no_external = heating_circuits.build_sensor_definitions([1])

        self.assertTrue(any(defn.key == "hk_status" for defn in hk2_only))
        self.assertFalse(any(defn.key == "hk3_status" for defn in hk2_only))
        self.assertTrue(any(defn.key == "hk3_status" for defn in hk2_hk3))
        self.assertFalse(
            any(defn.group == sensors.WeishauptDeviceGroup.HK for defn in no_external)
        )

    def test_heating_circuit_names_do_not_change_unique_ids(self) -> None:
        """Display names must not be part of unique IDs."""
        hk2_def = heating_circuits.build_hk_sensor_definitions(2, 0x01)[0]
        entity_a = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(data={}, heating_circuit_names={2: "A"}),
            sensor_def=hk2_def,
            entry=SimpleNamespace(entry_id="entry-123"),
        )
        entity_b = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(data={}, heating_circuit_names={2: "B"}),
            sensor_def=hk2_def,
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(entity_a._attr_unique_id, entity_b._attr_unique_id)

    def test_hk_select_unique_ids_do_not_collide_with_sensors(self) -> None:
        """HK2/HK3 selects should not reuse read-only sensor unique IDs."""
        for sensor_def in (
            heating_circuits.build_hk_sensor_definitions(2, 0x01)[0],
            heating_circuits.build_hk_sensor_definitions(3, 0x02)[0],
        ):
            sensor_entity = sensor.WeishauptSensorEntity(
                coordinator=SimpleNamespace(
                    data={}, heating_circuit_names={2: "HK2", 3: "HK3"}
                ),
                sensor_def=sensor_def,
                entry=SimpleNamespace(entry_id="entry-123"),
            )
            select_entity = select.WeishauptSelectEntity(
                coordinator=SimpleNamespace(
                    data={}, heating_circuit_names={2: "HK2", 3: "HK3"}
                ),
                sensor_def=sensor_def,
                entry=SimpleNamespace(entry_id="entry-123"),
            )

            self.assertNotEqual(
                sensor_entity._attr_unique_id,
                select_entity._attr_unique_id,
            )
            self.assertTrue(select_entity._attr_unique_id.endswith("_select"))


if __name__ == "__main__":
    unittest.main()
