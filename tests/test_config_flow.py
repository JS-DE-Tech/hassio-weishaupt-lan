"""Unit tests for config/options helper behavior."""

from __future__ import annotations

import importlib.util
from pathlib import Path
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
sys.modules["homeassistant.config_entries"] = config_entries

const_module = types.ModuleType("homeassistant.const")
const_module.CONF_HOST = "host"
const_module.CONF_PASSWORD = "password"
const_module.CONF_USERNAME = "username"
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
api_stub.WeishauptApiClient = object
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
        self.assertFalse(
            config_flow._normalize_user_input(
                {"scan_interval": 30}
            )["enable_experimental_wtc_sensors"]
        )

    async def test_options_store_experimental_boolean(self) -> None:
        """Options flow should store the experimental boolean."""
        flow = config_flow.WeishauptWemOptionsFlow(
            ConfigEntry(data={"scan_interval": 60}, options={})
        )

        result = await flow.async_step_init(
            {
                "scan_interval": 60,
                "enable_experimental_wtc_sensors": True,
            }
        )

        self.assertTrue(result["data"]["enable_experimental_wtc_sensors"])


if __name__ == "__main__":
    unittest.main()
