"""Unit tests for config/options helper behavior."""

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


voluptuous = types.ModuleType("voluptuous")
voluptuous.Schema = lambda schema: schema
voluptuous.Required = lambda key, default=None: key
voluptuous.Optional = lambda key, default=None: key
sys.modules.setdefault("voluptuous", voluptuous)

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

config_entries = types.ModuleType("homeassistant.config_entries")


class ConfigEntry:
    """Minimal config entry stub."""

    def __init__(self, data: dict, options: dict) -> None:
        self.data = data
        self.options = options


class ConfigFlow:
    """Minimal config flow stub."""

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__()

    def async_create_entry(self, title: str, data: dict) -> dict:
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(self, step_id: str, data_schema, errors=None) -> dict:
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    async def async_set_unique_id(self, unique_id: str) -> None:
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        return None


class OptionsFlowWithReload:
    """Minimal options flow stub."""

    def async_create_entry(self, title: str, data: dict) -> dict:
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(self, step_id: str, data_schema) -> dict:
        return {"type": "form", "step_id": step_id, "data_schema": data_schema}


config_entries.ConfigEntry = ConfigEntry
config_entries.ConfigFlow = ConfigFlow
config_entries.ConfigFlowResult = dict
config_entries.OptionsFlowWithReload = OptionsFlowWithReload
sys.modules["homeassistant.config_entries"] = config_entries

const_module = types.ModuleType("homeassistant.const")
const_module.CONF_HOST = "host"
const_module.CONF_PASSWORD = "password"
const_module.CONF_USERNAME = "username"
const_module.PERCENTAGE = "%"
const_module.UnitOfEnergy = SimpleNamespace(KILO_WATT_HOUR="kWh")
const_module.UnitOfPower = SimpleNamespace(KILO_WATT="kW")
const_module.UnitOfPressure = SimpleNamespace(BAR="bar")
const_module.UnitOfTemperature = SimpleNamespace(CELSIUS="C")
const_module.UnitOfTime = SimpleNamespace(HOURS="h")
sys.modules["homeassistant.const"] = const_module

helpers_pkg = types.ModuleType("homeassistant.helpers")
helpers_pkg.__path__ = []
sys.modules["homeassistant.helpers"] = helpers_pkg

aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
aiohttp_client.async_get_clientsession = lambda hass: None
sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client

selector = types.ModuleType("homeassistant.helpers.selector")


class NumberSelectorMode:
    """Minimal selector mode enum stub."""

    SLIDER = "slider"


class NumberSelectorConfig:
    """Minimal number selector config stub."""

    def __init__(
        self, min: int, max: int, step: int, mode: str, unit_of_measurement: str
    ) -> None:
        self.min = min
        self.max = max
        self.step = step
        self.mode = mode
        self.unit_of_measurement = unit_of_measurement


class NumberSelector:
    """Minimal number selector stub."""

    def __init__(self, config: NumberSelectorConfig) -> None:
        self.config = config


selector.NumberSelector = NumberSelector
selector.NumberSelectorConfig = NumberSelectorConfig
selector.NumberSelectorMode = NumberSelectorMode
helpers_pkg.selector = selector
sys.modules["homeassistant.helpers.selector"] = selector

aiohttp_stub = types.ModuleType("aiohttp")
aiohttp_stub.ClientSession = object
sys.modules.setdefault("aiohttp", aiohttp_stub)

custom_components_pkg = types.ModuleType("custom_components")
custom_components_pkg.__path__ = [str(REPO_ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components_pkg)

integration_pkg = types.ModuleType("custom_components.weishaupt_wtc_lan")
integration_pkg.__path__ = [str(PACKAGE_ROOT)]
sys.modules.setdefault("custom_components.weishaupt_wtc_lan", integration_pkg)

load_module("custom_components.weishaupt_wtc_lan.const", PACKAGE_ROOT / "const.py")
api_stub = types.ModuleType("custom_components.weishaupt_wtc_lan.api")


class ApiClientStub:
    """Placeholder API client stub."""


api_stub.WeishauptApiClient = ApiClientStub
api_stub.WeishauptAuthError = Exception
api_stub.WeishauptConnectionError = Exception
sys.modules["custom_components.weishaupt_wtc_lan.api"] = api_stub
config_flow = load_module(
    "custom_components.weishaupt_wtc_lan.config_flow",
    PACKAGE_ROOT / "config_flow.py",
)


class ConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    """Test config/options helpers."""

    def test_experimental_option_defaults_to_disabled(self) -> None:
        """The experimental option should be present and disabled by default."""
        schema = config_flow._options_schema({})

        self.assertIn("enable_experimental_wtc_sensors", schema)
        self.assertIn("enable_extended_experimental_wtc_sensors", schema)
        self.assertFalse(
            config_flow._normalize_user_input(
                {"scan_interval": 30}
            )["enable_experimental_wtc_sensors"]
        )
        self.assertFalse(
            config_flow._normalize_user_input(
                {"scan_interval": 30}
            )["enable_extended_experimental_wtc_sensors"]
        )

    def test_names_schema_and_detected_toggle_defaults(self) -> None:
        """Naming schema should expose detected-name toggle and HK fields."""
        schema = config_flow._names_schema({})

        self.assertIn("use_detected_heating_circuit_names", schema)
        self.assertIn("hk1_name", schema)
        normalized = config_flow._normalize_user_input(
            {
                "scan_interval": 30,
                "hk1_name": "  Manual  ",
                "use_detected_heating_circuit_names": True,
            }
        )
        self.assertTrue(normalized["use_detected_heating_circuit_names"])
        self.assertEqual(normalized["hk1_name"], "Manual")

    async def test_options_store_experimental_boolean(self) -> None:
        """Options flow should store the experimental boolean."""
        flow = config_flow.WeishauptWemOptionsFlow(
            ConfigEntry(data={"scan_interval": 60}, options={})
        )

        result = await flow.async_step_init(
            {
                "scan_interval": 60,
                "enable_experimental_wtc_sensors": True,
                "enable_extended_experimental_wtc_sensors": True,
                "use_detected_heating_circuit_names": False,
            }
        )

        self.assertTrue(result["data"]["enable_experimental_wtc_sensors"])
        self.assertTrue(result["data"]["enable_extended_experimental_wtc_sensors"])
        self.assertFalse(result["data"]["use_detected_heating_circuit_names"])

    async def test_initial_names_step_persists_detected_names_separately(self) -> None:
        """Initial setup should store parsed detected names apart from overrides."""
        flow = config_flow.WeishauptWemConfigFlow()
        flow._pending_user_input = {
            "host": "wem-sg",
            "username": "admin",
            "password": "Admin123",
            "scan_interval": 30,
        }
        flow._detected_heating_circuit_names = {
            1: "Plattenwaermetauscher",
            2: "Fussbodenheizung",
        }

        result = await flow.async_step_names(
            {
                "use_detected_heating_circuit_names": True,
                "hk1_name": "",
                "hk2_name": "Manual HK2",
                "hk3_name": "",
            }
        )

        self.assertEqual(
            result["data"]["detected_heating_circuit_names"],
            {"1": "Plattenwaermetauscher", "2": "Fussbodenheizung"},
        )
        self.assertEqual(result["data"]["hk2_name"], "Manual HK2")

    async def test_options_refresh_success_updates_persisted_detected_names(self) -> None:
        """Opening options should refresh and persist detected names on success."""
        updated: list[dict] = []

        class Client:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def fetch_systable_csv(self) -> str:
                return "1;HK1;Plattenwaermetauscher\n2;HK2;Fussbodenheizung\n"

        config_flow.WeishauptApiClient = Client
        flow = config_flow.WeishauptWemOptionsFlow(
            ConfigEntry(
                data={
                    "host": "wem-sg",
                    "username": "admin",
                    "password": "Admin123",
                    "detected_heating_circuit_names": {"1": "Alt HK1"},
                },
                options={},
            )
        )
        flow.hass = SimpleNamespace(
            config_entries=SimpleNamespace(
                async_update_entry=lambda entry, data: updated.append(data)
            )
        )

        await flow.async_step_init()

        self.assertEqual(
            updated[0]["detected_heating_circuit_names"],
            {"1": "Plattenwaermetauscher", "2": "Fussbodenheizung"},
        )
        self.assertEqual(
            flow._detected_heating_circuit_names,
            {1: "Plattenwaermetauscher", 2: "Fussbodenheizung"},
        )

    async def test_options_refresh_failure_reuses_last_detected_names(self) -> None:
        """Opening options should keep persisted names when refresh fails."""
        updated: list[dict] = []

        class Client:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def fetch_systable_csv(self):
                return None

        config_flow.WeishauptApiClient = Client
        flow = config_flow.WeishauptWemOptionsFlow(
            ConfigEntry(
                data={
                    "host": "wem-sg",
                    "username": "admin",
                    "password": "Admin123",
                    "detected_heating_circuit_names": {"1": "Persisted HK1"},
                },
                options={},
            )
        )
        flow.hass = SimpleNamespace(
            config_entries=SimpleNamespace(
                async_update_entry=lambda entry, data: updated.append(data)
            )
        )

        await flow.async_step_init()

        self.assertEqual(updated, [])
        self.assertEqual(flow._detected_heating_circuit_names, {1: "Persisted HK1"})


if __name__ == "__main__":
    unittest.main()
