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
sys.modules["homeassistant.components.sensor"] = sensor_component

select_component = types.ModuleType("homeassistant.components.select")


class SelectEntity:
    """Minimal select entity stub."""


select_component.SelectEntity = SelectEntity
sys.modules["homeassistant.components.select"] = select_component

number_component = types.ModuleType("homeassistant.components.number")


class NumberEntity:
    """Minimal number entity stub."""


number_component.NumberEntity = NumberEntity
number_component.NumberMode = SimpleNamespace(SLIDER="slider")
sys.modules["homeassistant.components.number"] = number_component

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
number = load_module(
    "custom_components.weishaupt_wtc.number", PACKAGE_ROOT / "number.py"
)


def sensor_by_key(key: str):
    """Return a sensor definition by key."""
    return next(sensor_def for sensor_def in sensors.ALL_SENSORS if sensor_def.key == key)


class SensorDeviceInfoTests(unittest.TestCase):
    """Test device registry metadata for sensor entities."""

    def test_system_device_has_no_via_device(self) -> None:
        """The SG device is the root of the device tree."""
        entity = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(data={}),
            sensor_def=sensor_by_key("sg_aussentemperatur"),
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(
            entity.device_info["identifiers"],
            {("weishaupt_wtc", "entry-123_sg")},
        )
        self.assertNotIn("via_device", entity.device_info)

    def test_hk1_moves_to_own_device_without_unique_id_change(self) -> None:
        """HK1 SG-addressed entities should attach to a logical HK1 device."""
        hk1_def = sensor_by_key("sg_betriebsart_hk1_vorgabe")
        entity = select.WeishauptSelectEntity(
            coordinator=SimpleNamespace(
                data={}, heating_circuit_names={1: "Fussbodenheizung EG"}
            ),
            sensor_def=hk1_def,
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(hk1_def.mi, 0x02)
        self.assertEqual(hk1_def.mx, 0x00)
        self.assertEqual(entity._attr_unique_id, "entry-123_sg_betriebsart_hk1_vorgabe")
        self.assertEqual(
            entity.device_info["identifiers"],
            {("weishaupt_wtc", "entry-123_hk1")},
        )
        self.assertEqual(entity.device_info["name"], "Fussbodenheizung EG")
        self.assertEqual(
            entity.device_info["via_device"],
            ("weishaupt_wtc", "entry-123_sg"),
        )

    def test_warm_water_entities_move_to_own_device(self) -> None:
        """Warm-water SG-addressed entities should attach to the WW device."""
        ww_def = sensor_by_key("sg_status_warmwasser")
        entity = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(data={}),
            sensor_def=ww_def,
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(entity._attr_unique_id, "entry-123_sg_status_warmwasser")
        self.assertEqual(
            entity.device_info["identifiers"],
            {("weishaupt_wtc", "entry-123_ww")},
        )
        self.assertEqual(entity.device_info["name"], "Weishaupt Warmwasser")
        self.assertEqual(
            entity.device_info["via_device"],
            ("weishaupt_wtc", "entry-123_sg"),
        )

    def test_warm_water_number_unique_ids_and_device(self) -> None:
        """WW setpoint sliders should be platform-specific and on WW device."""
        normal_def = sensor_by_key("sg_wwsolltemperatur_normal")
        entity = number.WeishauptNumberEntity(
            coordinator=SimpleNamespace(data={}),
            sensor_def=normal_def,
            entry=SimpleNamespace(entry_id="entry-123"),
            settings=number.NUMBER_SETTINGS[normal_def.key],
        )

        self.assertEqual(
            entity._attr_unique_id,
            "entry-123_sg_wwsolltemperatur_normal_number",
        )
        self.assertEqual(entity._attr_native_min_value, 50.0)
        self.assertEqual(entity._attr_native_max_value, 60.0)
        self.assertEqual(entity._attr_native_step, 1.0)
        self.assertEqual(
            entity.device_info["identifiers"],
            {("weishaupt_wtc", "entry-123_ww")},
        )

    def test_systembetriebsart_select_uses_system_device(self) -> None:
        """System operating mode should be exposed as a system select."""
        system_def = sensor_by_key("sg_systembetriebsart")
        entity = select.WeishauptSelectEntity(
            coordinator=SimpleNamespace(
                data={"sg_systembetriebsart": {"value_int": 3}},
            ),
            sensor_def=system_def,
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(entity._attr_unique_id, "entry-123_sg_systembetriebsart")
        self.assertEqual(entity.options, ["Standby", "Sommer", "Automatik"])
        self.assertEqual(entity.current_option, "Automatik")
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

    def test_wtc_abgastemperatur_mapping_and_sentinel_values(self) -> None:
        """Abgastemperatur should stay on WTC and handle sentinel values."""
        abgas_def = sensor_by_key("wtc_abgastemperatur")
        entity = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(
                data={"wtc_abgastemperatur": {"value_int": 725, "value_hex": "02d5"}}
            ),
            sensor_def=abgas_def,
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(abgas_def.mi, 0x07)
        self.assertEqual(abgas_def.mx, 0x00)
        self.assertEqual(abgas_def.ox, 0x2533)
        self.assertEqual(abgas_def.os, 0x02)
        self.assertEqual(abgas_def.vs, 2)
        self.assertEqual(abgas_def.modbus_reg, "167")
        self.assertEqual(entity.native_value, 72.5)
        self.assertEqual(
            entity.device_info["identifiers"],
            {("weishaupt_wtc", "entry-123_wtc")},
        )

        entity.coordinator.data["wtc_abgastemperatur"] = {
            "value_int": 0x8000,
            "value_hex": "8000",
        }
        self.assertIsNone(entity.native_value)
        entity.coordinator.data["wtc_abgastemperatur"] = {
            "value_int": 0xFFFF,
            "value_hex": "ffff",
        }
        self.assertIsNone(entity.native_value)

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
        active_groups = {
            heating_circuits.DEVICE_GROUP_SYSTEM,
            heating_circuits.DEVICE_GROUP_WTC,
            heating_circuits.DEVICE_GROUP_WW,
        }
        hk2_only = heating_circuits.build_sensor_definitions([1, 2], active_groups)
        hk2_hk3 = heating_circuits.build_sensor_definitions([1, 2, 3], active_groups)
        no_external = heating_circuits.build_sensor_definitions([1], active_groups)

        self.assertTrue(any(defn.key == "hk_status" for defn in hk2_only))
        self.assertFalse(any(defn.key == "hk3_status" for defn in hk2_only))
        self.assertTrue(any(defn.key == "hk3_status" for defn in hk2_hk3))
        self.assertFalse(any(defn.key == "sol_kollektortemperatur" for defn in hk2_hk3))
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

    def test_confirmed_device_frames_render_expected_entity_states(self) -> None:
        """Confirmed raw responses should render the expected HA states."""
        hk1_def = sensor_by_key("sg_betriebsart_hk1_vorgabe")
        hk2_def = heating_circuits.build_hk_sensor_definitions(2, 0x01)[0]
        hk3_def = heating_circuits.build_hk_sensor_definitions(3, 0x02)[0]
        system_def = sensor_by_key("sg_systembetriebsart")
        abgas_def = sensor_by_key("wtc_abgastemperatur")
        coordinator = SimpleNamespace(
            data={
                hk1_def.key: {"value_int": 2, "value_hex": "02"},
                hk2_def.key: {"value_int": 2, "value_hex": "02"},
                hk3_def.key: {"value_int": 2, "value_hex": "02"},
                system_def.key: {"value_int": 2, "value_hex": "02"},
                abgas_def.key: {"value_int": 407, "value_hex": "0197"},
            },
            heating_circuit_names={},
        )
        entry = SimpleNamespace(entry_id="entry-123")

        hk1_select = select.WeishauptSelectEntity(coordinator, hk1_def, entry)
        hk2_select = select.WeishauptSelectEntity(coordinator, hk2_def, entry)
        hk3_select = select.WeishauptSelectEntity(coordinator, hk3_def, entry)
        system_select = select.WeishauptSelectEntity(coordinator, system_def, entry)
        abgas_sensor = sensor.WeishauptSensorEntity(coordinator, abgas_def, entry)

        self.assertEqual(hk1_select.current_option, "Zeitprogramm 1")
        self.assertEqual(hk2_select.current_option, "Zeitprogramm 1")
        self.assertEqual(hk3_select.current_option, "Zeitprogramm 1")
        self.assertEqual(system_select.current_option, "Sommer")
        self.assertTrue(abgas_sensor.available)
        self.assertEqual(abgas_sensor.native_value, 40.7)

    def test_confirmed_wtc_frames_render_valid_zero_values(self) -> None:
        """Confirmed WTC frames should not treat raw zero as unavailable."""
        keys_and_expected = {
            "wtc_anlagendruck": (149, "0095", 1.49),
            "wtc_kesseltemperatur": (402, "0192", 40.2),
            "wtc_volumenstrom_vpt": (0, "0000", 0),
            "wtc_abgastemperatur": (399, "018f", 39.9),
            "wtc_ruecklauftemperatur": (413, "019d", 41.3),
            "wtc_vorlaufsolltemperatur": (80, "0050", 8.0),
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
            self.assertEqual(entity.extra_state_attributes["raw_value_int"], _raw)

    def test_heating_circuit_current_mode_and_status_are_retained(self) -> None:
        """HK1, HK2 and HK3 should keep current-mode and status sensors."""
        active_groups = {
            heating_circuits.DEVICE_GROUP_SYSTEM,
            heating_circuits.DEVICE_GROUP_WTC,
            heating_circuits.DEVICE_GROUP_WW,
        }
        definitions = heating_circuits.build_sensor_definitions([1, 2, 3], active_groups)
        keys = {sensor_def.key for sensor_def in definitions}

        self.assertIn("sg_betriebsart_hk1_aktuell", keys)
        self.assertIn("sg_status_hk1", keys)
        self.assertIn("hk_betriebsart_aktuell", keys)
        self.assertIn("hk_status", keys)
        self.assertIn("hk3_betriebsart_aktuell", keys)
        self.assertIn("hk3_status", keys)

    def test_systable_csv_detects_optional_groups_without_solar(self) -> None:
        """systable.csv should be usable as primary optional device inventory."""
        csv_text = "id;name\n1;WTC Kessel\n2;EM-WW Warmwasser\n"

        groups = heating_circuits.device_groups_from_systable_csv(csv_text)

        self.assertIn(heating_circuits.DEVICE_GROUP_WTC, groups)
        self.assertIn(heating_circuits.DEVICE_GROUP_WW, groups)
        self.assertNotIn(heating_circuits.DEVICE_GROUP_SOL, groups)


if __name__ == "__main__":
    unittest.main()
