"""Unit tests for config/options helper behavior."""

from __future__ import annotations

import importlib.util
from pathlib import Path
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


voluptuous = types.ModuleType("voluptuous")
voluptuous.Schema = lambda schema: schema
voluptuous.Required = lambda key, default=None: key
voluptuous.Optional = lambda key, default=None: key
sys.modules.setdefault("voluptuous", voluptuous)

homeassistant_pkg = types.ModuleType("homeassistant")
homeassistant_pkg.__path__ = []
sys.modules.setdefault("homeassistant", homeassistant_pkg)

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
sys.modules.setdefault("homeassistant.config_entries", config_entries)

const_module = types.ModuleType("homeassistant.const")
const_module.CONF_HOST = "host"
const_module.CONF_PASSWORD = "password"
const_module.CONF_USERNAME = "username"
const_module.PERCENTAGE = "%"
const_module.UnitOfEnergy = types.SimpleNamespace(KILO_WATT_HOUR="kWh")
const_module.UnitOfPower = types.SimpleNamespace(KILO_WATT="kW")
const_module.UnitOfPressure = types.SimpleNamespace(BAR="bar")
const_module.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")
const_module.UnitOfTime = types.SimpleNamespace(HOURS="h")
sys.modules.setdefault("homeassistant.const", const_module)

helpers_pkg = types.ModuleType("homeassistant.helpers")
helpers_pkg.__path__ = []
sys.modules.setdefault("homeassistant.helpers", helpers_pkg)

aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
aiohttp_client.async_get_clientsession = lambda hass: None
sys.modules.setdefault("homeassistant.helpers.aiohttp_client", aiohttp_client)

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
sys.modules.setdefault("homeassistant.helpers.selector", selector)

aiohttp_stub = types.ModuleType("aiohttp")
aiohttp_stub.ClientSession = object
sys.modules.setdefault("aiohttp", aiohttp_stub)

custom_components_pkg = types.ModuleType("custom_components")
custom_components_pkg.__path__ = [str(REPO_ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components_pkg)

integration_pkg = types.ModuleType("custom_components.weishaupt_wtc")
integration_pkg.__path__ = [str(PACKAGE_ROOT)]
sys.modules.setdefault("custom_components.weishaupt_wtc", integration_pkg)

load_module("custom_components.weishaupt_wtc.const", PACKAGE_ROOT / "const.py")
api_stub = types.ModuleType("custom_components.weishaupt_wtc.api")
api_stub.WeishauptApiClient = object
api_stub.WeishauptAuthError = Exception
api_stub.WeishauptConnectionError = Exception
sys.modules["custom_components.weishaupt_wtc.api"] = api_stub
config_flow = load_module(
    "custom_components.weishaupt_wtc.config_flow", PACKAGE_ROOT / "config_flow.py"
)


class ConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    """Test config/options helpers."""

    def test_scan_interval_selector_uses_required_slider_bounds(self) -> None:
        """The setup/options field should use the requested HA slider config."""
        config = config_flow.SCAN_INTERVAL_SELECTOR.config

        self.assertEqual(config.min, 30)
        self.assertEqual(config.max, 300)
        self.assertEqual(config.step, 10)
        self.assertEqual(config.mode, "slider")
        self.assertEqual(config.unit_of_measurement, "s")

    def test_scan_interval_default_is_30(self) -> None:
        """Invalid or missing values should fall back to 30 seconds."""
        self.assertEqual(config_flow._scan_interval_default(None), 30)
        self.assertEqual(config_flow._scan_interval_default("invalid"), 30)

    async def test_options_value_overrides_setup_value(self) -> None:
        """Options defaults should win over initial setup values."""
        flow = config_flow.WeishauptWemOptionsFlow(
            ConfigEntry(
                data={"scan_interval": 60, "hk1_name": "Setup HK1"},
                options={"scan_interval": 120, "hk1_name": "Options HK1"},
            )
        )

        result = await flow.async_step_init(
            {"scan_interval": 120, "hk1_name": "Options HK1"}
        )

        self.assertEqual(result["data"]["scan_interval"], 120)
        self.assertEqual(result["data"]["hk1_name"], "Options HK1")


if __name__ == "__main__":
    unittest.main()
