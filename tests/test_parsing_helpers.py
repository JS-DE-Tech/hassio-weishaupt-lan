"""Unit tests for parsing and naming helpers."""

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
sensor_component.SensorDeviceClass = SimpleNamespace(
    TEMPERATURE="temperature",
    PRESSURE="pressure",
    POWER="power",
    ENERGY="energy",
    TIMESTAMP="timestamp",
)
sensor_component.SensorStateClass = SimpleNamespace(
    MEASUREMENT="measurement",
    TOTAL="total",
    TOTAL_INCREASING="total_increasing",
)
sys.modules["homeassistant.components.sensor"] = sensor_component

const = types.ModuleType("homeassistant.const")
const.PERCENTAGE = "%"
const.UnitOfEnergy = SimpleNamespace(KILO_WATT_HOUR="kWh")
const.UnitOfPower = SimpleNamespace(KILO_WATT="kW")
const.UnitOfPressure = SimpleNamespace(BAR="bar")
const.UnitOfTemperature = SimpleNamespace(CELSIUS="C")
const.UnitOfTime = SimpleNamespace(HOURS="h")
sys.modules["homeassistant.const"] = const

custom_components_pkg = types.ModuleType("custom_components")
custom_components_pkg.__path__ = [str(REPO_ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components_pkg)

integration_pkg = types.ModuleType("custom_components.weishaupt_wtc_lan")
integration_pkg.__path__ = [str(PACKAGE_ROOT)]
sys.modules.setdefault("custom_components.weishaupt_wtc_lan", integration_pkg)

load_module("custom_components.weishaupt_wtc_lan.const", PACKAGE_ROOT / "const.py")
parsing = load_module(
    "custom_components.weishaupt_wtc_lan.parsing", PACKAGE_ROOT / "parsing.py"
)
load_module("custom_components.weishaupt_wtc_lan.sensors", PACKAGE_ROOT / "sensors.py")
heating_circuits = load_module(
    "custom_components.weishaupt_wtc_lan.heating_circuits",
    PACKAGE_ROOT / "heating_circuits.py",
)


class ParsingHelperTests(unittest.TestCase):
    """Test pure parsing helpers."""

    def test_device_date_and_time_helpers_validate_ranges(self) -> None:
        """Date/time helpers should format valid values and reject invalid ones."""
        values = {
            "sg_datum_tag": 11,
            "sg_datum_monat": 6,
            "sg_datum_jahr": 26,
            "sg_uhrzeit_stunden": 17,
            "sg_uhrzeit_minuten": 25,
        }
        self.assertEqual(parsing.build_device_date(values), "11.06.2026")
        self.assertEqual(parsing.build_device_clock_time(values), "17:25")
        self.assertIsNone(parsing.build_device_date({**values, "sg_datum_tag": 31, "sg_datum_monat": 2}))
        self.assertIsNone(parsing.build_device_clock_time({**values, "sg_uhrzeit_stunden": 24}))

    def test_decode_ipv4_from_hex_and_integer(self) -> None:
        """IPv4 helpers should decode big-endian four-byte values."""
        self.assertEqual(parsing.decode_ipv4(0, "c0a8012a"), "192.168.1.42")
        self.assertEqual(parsing.decode_ipv4(0x08080808), "8.8.8.8")
        self.assertIsNone(parsing.decode_ipv4(-1))

    def test_format_mac_address(self) -> None:
        """MAC helpers should format six byte components."""
        self.assertEqual(
            parsing.format_mac_address([0, 0x11, 0x22, 0xAA, 0xBB, 0xCC]),
            "00-11-22-AA-BB-CC",
        )
        self.assertIsNone(parsing.format_mac_address([0, 1, 2]))
        self.assertIsNone(parsing.format_mac_address([0, 1, 2, 3, 4, 0x100]))

    def test_heating_circuit_names_from_systable_csv(self) -> None:
        """Detected heating-circuit names should come from CSV-like rows."""
        csv_text = (
            "id;module;display\n"
            "1;HK1;Plattenwaermetauscher\n"
            "2;Heizkreis 2;Fussbodenheizung\n"
            "3;HK3 -> Heizkoerper\n"
        )
        self.assertEqual(
            heating_circuits.heating_circuit_names_from_systable_csv(csv_text),
            {
                1: "Plattenwaermetauscher",
                2: "Fussbodenheizung",
                3: "Heizkoerper",
            },
        )

    def test_real_systable_fixture_parsing(self) -> None:
        """Real systable rows should distinguish HK and logical device names."""
        csv_text = (REPO_ROOT / "tests" / "fixtures" / "real_systable.csv").read_text(
            encoding="utf-8-sig"
        )

        self.assertEqual(
            heating_circuits.heating_circuit_names_from_systable_csv(csv_text),
            {
                1: "Plattenwaermetauscher",
                2: "Fussbodenheizung",
                3: "Heizkoerper",
            },
        )
        self.assertEqual(
            heating_circuits.logical_device_names_from_systable_csv(csv_text),
            {
                "system": "HeizungSAB7",
                "ww": "Warmwasserspeicher",
                "network": "GATEWAY0",
                "wtc": "WE0",
            },
        )
        self.assertNotIn(
            "Warmwasserspeicher",
            heating_circuits.heating_circuit_names_from_systable_csv(csv_text).values(),
        )

    def test_heating_circuit_name_resolution_order(self) -> None:
        """Manual overrides win, then detected names, then generic fallbacks."""
        resolved = heating_circuits.resolve_heating_circuit_names(
            {1: "Manual HK1", 2: "", 3: None},
            {1: "Detected HK1", 2: "Detected HK2"},
            True,
            {1: "Heizkreis 1", 2: "Heizkreis 2", 3: "Heizkreis 3"},
        )
        self.assertEqual(resolved[1], "Manual HK1")
        self.assertEqual(resolved[2], "Detected HK2")
        self.assertEqual(resolved[3], "Heizkreis 3")

    def test_detected_name_config_serialization(self) -> None:
        """Detected names should persist with string keys and normalize on read."""
        stored = heating_circuits.serialize_heating_circuit_names(
            {1: " Plattenwaermetauscher ", 2: "", 3: "Heizkoerper"}
        )

        self.assertEqual(
            stored,
            {"1": "Plattenwaermetauscher", "3": "Heizkoerper"},
        )
        self.assertEqual(
            heating_circuits.heating_circuit_names_from_config(stored),
            {1: "Plattenwaermetauscher", 3: "Heizkoerper"},
        )


if __name__ == "__main__":
    unittest.main()
