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

select_component = types.ModuleType("homeassistant.components.select")


class SelectEntity:
    """Minimal select entity stub."""


select_component.SelectEntity = SelectEntity
sys.modules["homeassistant.components.select"] = select_component

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
select_platform = load_module(
    "custom_components.weishaupt_wtc_lan.select", PACKAGE_ROOT / "select.py"
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
        self.assertEqual(attrs["confidence"], "candidate")
        self.assertEqual(attrs["probable_unit"], "°C")
        self.assertEqual(attrs["probable_scale"], 0.1)

    def test_vpt_power_zero_is_valid_for_adaptive_value_sizes(self) -> None:
        """WTC VPT power should expose raw zero as 0.0 kW for VS=4 and VS=2."""
        sensor_def = sensor_by_key("wtc_waermeleistung_vpt")
        entry = SimpleNamespace(entry_id="entry-123")
        for value_size, raw_hex in ((4, "00000000"), (2, "0000")):
            coordinator = SimpleNamespace(
                data={
                    sensor_def.key: {
                        "value_int": 0,
                        "value_hex": raw_hex,
                    }
                },
            )
            entity = sensor.WeishauptSensorEntity(
                coordinator=coordinator,
                sensor_def=types.SimpleNamespace(
                    **{**sensor_def.__dict__, "vs": value_size}
                ),
                entry=entry,
            )
            self.assertTrue(entity.available)
            self.assertEqual(entity.native_value, 0.0)

    def test_device_date_and_clock_time_are_derived_from_components(self) -> None:
        """Separate device date/time sensors should use existing SG components."""
        coordinator = SimpleNamespace(
            data={
                "sg_uhrzeit_stunden": {"value_int": 17, "value_hex": "11"},
                "sg_uhrzeit_minuten": {"value_int": 25, "value_hex": "19"},
                "sg_datum_tag": {"value_int": 11, "value_hex": "0b"},
                "sg_datum_monat": {"value_int": 6, "value_hex": "06"},
                "sg_datum_jahr": {"value_int": 26, "value_hex": "1a"},
            },
        )
        entry = SimpleNamespace(entry_id="entry-123")

        date_entity = sensor.WeishauptSensorEntity(
            coordinator=coordinator,
            sensor_def=sensor_by_key("sg_device_date"),
            entry=entry,
        )
        time_entity = sensor.WeishauptSensorEntity(
            coordinator=coordinator,
            sensor_def=sensor_by_key("sg_device_clock_time"),
            entry=entry,
        )

        self.assertTrue(date_entity.available)
        self.assertEqual(date_entity.native_value, "11.06.2026")
        self.assertTrue(time_entity.available)
        self.assertEqual(time_entity.native_value, "17:25")

    def test_device_date_clock_time_and_combined_timestamp_use_corrected_order(self) -> None:
        """Raw date registers should map year/month/day in validated hardware order."""
        self.assertEqual(sensor_by_key("sg_datum_jahr").os, 0x02)
        self.assertEqual(sensor_by_key("sg_datum_monat").os, 0x03)
        self.assertEqual(sensor_by_key("sg_datum_tag").os, 0x04)
        coordinator = SimpleNamespace(
            data={
                "sg_uhrzeit_stunden": {"value_int": 22, "value_hex": "16"},
                "sg_uhrzeit_minuten": {"value_int": 26, "value_hex": "1a"},
                "sg_datum_jahr": {"value_int": 26, "value_hex": "1a"},
                "sg_datum_monat": {"value_int": 6, "value_hex": "06"},
                "sg_datum_tag": {"value_int": 11, "value_hex": "0b"},
            },
        )
        entry = SimpleNamespace(entry_id="entry-123")
        date_entity = sensor.WeishauptSensorEntity(
            coordinator=coordinator,
            sensor_def=sensor_by_key("sg_device_date"),
            entry=entry,
        )
        clock_entity = sensor.WeishauptSensorEntity(
            coordinator=coordinator,
            sensor_def=sensor_by_key("sg_device_clock_time"),
            entry=entry,
        )
        timestamp_entity = sensor.WeishauptSensorEntity(
            coordinator=coordinator,
            sensor_def=sensor_by_key("sg_device_time"),
            entry=entry,
        )

        self.assertEqual(date_entity.native_value, "11.06.2026")
        self.assertEqual(clock_entity.native_value, "22:26")
        self.assertEqual(timestamp_entity.native_value, "2026-06-11T22:26:00+00:00")

    def test_invalid_derived_date_is_unavailable(self) -> None:
        """Invalid component combinations should make the derived date unavailable."""
        entity = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(
                data={
                    "sg_datum_jahr": {"value_int": 26, "value_hex": "1a"},
                    "sg_datum_monat": {"value_int": 2, "value_hex": "02"},
                    "sg_datum_tag": {"value_int": 31, "value_hex": "1f"},
                }
            ),
            sensor_def=sensor_by_key("sg_device_date"),
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertFalse(entity.available)
        self.assertIsNone(entity.native_value)

    def test_derived_date_time_defaults_and_raw_component_defaults(self) -> None:
        """Derived date/time should be enabled while raw components remain disabled."""
        self.assertTrue(sensor_by_key("sg_device_date").entity_registry_enabled_default)
        self.assertTrue(
            sensor_by_key("sg_device_clock_time").entity_registry_enabled_default
        )
        self.assertFalse(sensor_by_key("sg_device_time").entity_registry_enabled_default)
        for key in (
            "sg_uhrzeit_stunden",
            "sg_uhrzeit_minuten",
            "sg_datum_tag",
            "sg_datum_monat",
            "sg_datum_jahr",
        ):
            self.assertFalse(sensor_by_key(key).entity_registry_enabled_default)

    def test_network_values_render_on_network_device(self) -> None:
        """Network diagnostics should decode IPv4 values and use their own device."""
        ip_def = next(
            item for item in sensors.NETWORK_SENSORS if item.key == "network_ip_address"
        )
        host_def = next(
            item for item in sensors.NETWORK_SENSORS if item.key == "network_hostname"
        )
        coordinator = SimpleNamespace(
            data={
                "network_ip_address": {
                    "value_int": 0xC0A8012A,
                    "value_hex": "c0a8012a",
                },
                "network_hostname": {
                    "value_int": 0,
                    "value_hex": "57454d2d534700",
                    "value_string": "WEM-SG",
                },
            },
        )
        entry = SimpleNamespace(entry_id="entry-123")

        ip_entity = sensor.WeishauptSensorEntity(
            coordinator=coordinator,
            sensor_def=ip_def,
            entry=entry,
        )
        host_entity = sensor.WeishauptSensorEntity(
            coordinator=coordinator,
            sensor_def=host_def,
            entry=entry,
        )

        self.assertEqual(ip_entity.native_value, "192.168.1.42")
        self.assertEqual(host_entity.native_value, "WEM-SG")
        self.assertEqual(
            ip_entity.device_info["identifiers"],
            {("weishaupt_wtc_lan", "entry-123_network")},
        )
        self.assertEqual(ip_entity.device_info["name"], "Weishaupt Systemgerät Netzwerk")

    def test_network_numeric_entities_enabled_and_ip_mode_raw_3_is_dhcp(self) -> None:
        """Network numeric diagnostics should be enabled and map raw 3 to DHCP."""
        mode_def = next(
            item for item in sensors.NETWORK_SENSORS if item.key == "network_ip_mode"
        )
        self.assertFalse(any(item.poll for item in sensors.NETWORK_SENSORS))
        self.assertTrue(mode_def.entity_registry_enabled_default)
        entity = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(
                data={"network_ip_mode": {"value_int": 3, "value_hex": "03"}}
            ),
            sensor_def=mode_def,
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(entity.native_value, "DHCP")

    def test_system_operating_mode_current_mirrors_existing_data(self) -> None:
        """System operating-mode display should mirror the existing writable register."""
        entity = sensor.WeishauptSensorEntity(
            coordinator=SimpleNamespace(
                data={"sg_systembetriebsart": {"value_int": 2, "value_hex": "02"}}
            ),
            sensor_def=sensor_by_key("sg_systembetriebsart_aktuell"),
            entry=SimpleNamespace(entry_id="entry-123"),
        )

        self.assertTrue(entity.available)
        self.assertEqual(entity.native_value, "Sommer")

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
            extended_experimental_wtc_registers=[],
        )
        hass = SimpleNamespace(data={"weishaupt_wtc_lan": {"entry-123": coordinator}})

        await sensor.async_setup_entry(
            hass,
            SimpleNamespace(entry_id="entry-123"),
            lambda entities: added.extend(entities),
        )

        self.assertEqual(added, [])
        self.assertEqual(len(registry.created), 1)

    async def test_sensor_setup_skips_writable_setpoints_but_keeps_actual_states(self) -> None:
        """Read-only duplicate setpoint sensors should not be created for HK circuits."""
        registry = DeviceRegistry()
        sensor.dr.async_get = lambda hass: registry
        added: list = []
        coordinator = SimpleNamespace(
            sensor_definitions=[
                sensor_by_key("sg_betriebsart_hk1_vorgabe"),
                sensor_by_key("sg_betriebsart_hk1_aktuell"),
                next(item for item in sensors.HK_SENSORS if item.key == "hk_betriebsart_vorgabe"),
                next(item for item in sensors.HK_SENSORS if item.key == "hk_betriebsart_aktuell"),
            ],
            experimental_wtc_registers=[],
            extended_experimental_wtc_registers=[],
        )
        hass = SimpleNamespace(data={"weishaupt_wtc_lan": {"entry-123": coordinator}})

        await sensor.async_setup_entry(
            hass,
            SimpleNamespace(entry_id="entry-123"),
            lambda entities: added.extend(entities),
        )

        self.assertEqual(
            {entity._attr_unique_id for entity in added},
            {
                "entry-123_sg_betriebsart_hk1_aktuell",
                "entry-123_hk_betriebsart_aktuell",
            },
        )

    async def test_select_setup_keeps_writable_hk1_hk2_hk3_setpoints(self) -> None:
        """Writable operating-mode selects should remain for every detected circuit."""
        hk2 = next(item for item in sensors.HK_SENSORS if item.key == "hk_betriebsart_vorgabe")
        hk3 = heating_circuits.build_hk_sensor_definitions(3, 0x02)[0]
        coordinator = SimpleNamespace(
            sensor_definitions=[
                sensor_by_key("sg_betriebsart_hk1_vorgabe"),
                hk2,
                hk3,
                sensor_by_key("sg_systembetriebsart"),
            ],
            data={
                "sg_betriebsart_hk1_vorgabe": {"value_int": 5, "value_hex": "05"},
                "hk_betriebsart_vorgabe": {"value_int": 2, "value_hex": "02"},
                "hk3_betriebsart_vorgabe": {"value_int": 2, "value_hex": "02"},
                "sg_systembetriebsart": {"value_int": 2, "value_hex": "02"},
            },
        )
        added: list = []

        await select_platform.async_setup_entry(
            SimpleNamespace(data={"weishaupt_wtc_lan": {"entry-123": coordinator}}),
            SimpleNamespace(entry_id="entry-123"),
            lambda entities: added.extend(entities),
        )

        self.assertEqual(
            {entity._sensor_def.key for entity in added},
            {
                "sg_betriebsart_hk1_vorgabe",
                "hk_betriebsart_vorgabe",
                "hk3_betriebsart_vorgabe",
                "sg_systembetriebsart",
            },
        )
        hk2_select = next(
            entity for entity in added if entity._sensor_def.key == "hk_betriebsart_vorgabe"
        )
        self.assertEqual(hk2_select.current_option, "Zeitprogramm 1")


if __name__ == "__main__":
    unittest.main()
