"""Unit tests for setup-time experimental probing and cleanup helpers."""

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


aiohttp_stub = types.ModuleType("aiohttp")
aiohttp_stub.ClientConnectorError = Exception
aiohttp_stub.BasicAuth = lambda *args, **kwargs: None
aiohttp_stub.ClientTimeout = lambda *args, **kwargs: None
aiohttp_stub.ClientSession = object
sys.modules["aiohttp"] = aiohttp_stub

homeassistant_pkg = types.ModuleType("homeassistant")
homeassistant_pkg.__path__ = []
sys.modules["homeassistant"] = homeassistant_pkg

components_pkg = types.ModuleType("homeassistant.components")
components_pkg.__path__ = []
sys.modules["homeassistant.components"] = components_pkg

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
config_entries.ConfigEntry = object
sys.modules["homeassistant.config_entries"] = config_entries

const = types.ModuleType("homeassistant.const")
const.CONF_HOST = "host"
const.CONF_PASSWORD = "password"
const.CONF_USERNAME = "username"
const.Platform = SimpleNamespace(
    SENSOR="sensor",
    SELECT="select",
    NUMBER="number",
    BUTTON="button",
)
const.PERCENTAGE = "%"
const.UnitOfEnergy = SimpleNamespace(KILO_WATT_HOUR="kWh")
const.UnitOfPower = SimpleNamespace(KILO_WATT="kW")
const.UnitOfPressure = SimpleNamespace(BAR="bar")
const.UnitOfTemperature = SimpleNamespace(CELSIUS="C")
const.UnitOfTime = SimpleNamespace(HOURS="h")
sys.modules["homeassistant.const"] = const

core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
sys.modules["homeassistant.core"] = core

helpers_pkg = types.ModuleType("homeassistant.helpers")
helpers_pkg.__path__ = []
sys.modules["homeassistant.helpers"] = helpers_pkg

aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
aiohttp_client.async_get_clientsession = lambda hass: None
sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client

device_registry_module = types.ModuleType("homeassistant.helpers.device_registry")
entity_registry_module = types.ModuleType("homeassistant.helpers.entity_registry")
sys.modules["homeassistant.helpers.device_registry"] = device_registry_module
sys.modules["homeassistant.helpers.entity_registry"] = entity_registry_module
helpers_pkg.device_registry = device_registry_module
helpers_pkg.entity_registry = entity_registry_module

update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")


class DataUpdateCoordinator:
    """Minimal coordinator base."""

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, *args, **kwargs) -> None:
        pass


update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
update_coordinator.UpdateFailed = Exception
sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

custom_components_pkg = types.ModuleType("custom_components")
custom_components_pkg.__path__ = [str(REPO_ROOT / "custom_components")]
sys.modules["custom_components"] = custom_components_pkg

integration_pkg = types.ModuleType("custom_components.weishaupt_wtc_lan")
integration_pkg.__path__ = [str(PACKAGE_ROOT)]
sys.modules["custom_components.weishaupt_wtc_lan"] = integration_pkg

load_module("custom_components.weishaupt_wtc_lan.const", PACKAGE_ROOT / "const.py")
load_module("custom_components.weishaupt_wtc_lan.api", PACKAGE_ROOT / "api.py")
load_module("custom_components.weishaupt_wtc_lan.sensors", PACKAGE_ROOT / "sensors.py")
load_module(
    "custom_components.weishaupt_wtc_lan.heating_circuits",
    PACKAGE_ROOT / "heating_circuits.py",
)
load_module(
    "custom_components.weishaupt_wtc_lan.coordinator",
    PACKAGE_ROOT / "coordinator.py",
)
integration = load_module(
    "custom_components.weishaupt_wtc_lan", PACKAGE_ROOT / "__init__.py"
)


class FakeClient:
    """Fake API client for experimental setup probes."""

    def __init__(self, supported_keys: set[str]) -> None:
        self.supported_keys = supported_keys
        self.params: list[dict] = []

    async def read_parameters(self, params: list[dict]) -> dict:
        self.params = params
        return {
            param["key"]: {"value_int": 0, "value_hex": "00"}
            for param in params
            if param["key"] in self.supported_keys
        }


class EntityRegistry:
    """Minimal entity registry."""

    def __init__(self, entries: list[SimpleNamespace]) -> None:
        self.entries = entries
        self.removed: list[str] = []

    def async_remove(self, entity_id: str) -> None:
        self.removed.append(entity_id)
        self.entries = [entry for entry in self.entries if entry.entity_id != entity_id]


class DeviceRegistry:
    """Minimal device registry."""

    def __init__(self, device) -> None:
        self.device = device
        self.removed: list[str] = []

    def async_get_device(self, identifiers: set[tuple[str, str]]):
        if self.device and self.device.identifiers == identifiers:
            return self.device
        return None

    def async_remove_device(self, device_id: str) -> None:
        self.removed.append(device_id)


class IntegrationHelperTests(unittest.IsolatedAsyncioTestCase):
    """Test setup helper behavior."""

    async def test_probe_experimental_registers_keeps_only_supported_candidates(self) -> None:
        """Setup probe should keep CMD_RESPONSE candidates and skip errors."""
        supported = {
            "wtc_experimental_09_01_2612_02_02",
            "wtc_experimental_09_01_2619_02_01",
            "wtc_experimental_09_01_2904_00_01",
        }
        client = FakeClient(supported)

        registers = await integration._async_probe_experimental_wtc_registers(client)

        self.assertEqual({register.key for register in registers}, supported)
        self.assertEqual(len(client.params), 19)

    async def test_cleanup_removes_stale_experimental_device_without_foreign_entries(
        self,
    ) -> None:
        """Cleanup should remove only stale integration-owned device contents."""
        device = SimpleNamespace(
            id="device-1",
            identifiers={("weishaupt_wtc_lan", "entry-123_wtc_experimental")},
        )
        entries = [
            SimpleNamespace(
                entity_id="sensor.experimental",
                config_entry_id="entry-123",
            )
        ]
        entity_registry = EntityRegistry(entries)
        device_registry = DeviceRegistry(device)
        integration.er.async_get = lambda hass: entity_registry
        integration.dr.async_get = lambda hass: device_registry
        integration.er.async_entries_for_device = (
            lambda registry, device_id: list(registry.entries)
        )

        await integration._async_cleanup_inactive_devices(
            hass=object(),
            entry=SimpleNamespace(entry_id="entry-123"),
            inactive_suffixes={"wtc_experimental"},
        )

        self.assertEqual(entity_registry.removed, ["sensor.experimental"])
        self.assertEqual(device_registry.removed, ["device-1"])

    async def test_cleanup_skips_device_with_foreign_entities(self) -> None:
        """Cleanup should not remove devices containing unrelated entities."""
        device = SimpleNamespace(
            id="device-1",
            identifiers={("weishaupt_wtc_lan", "entry-123_wtc_experimental")},
        )
        entries = [
            SimpleNamespace(
                entity_id="sensor.foreign",
                config_entry_id="other-entry",
            )
        ]
        entity_registry = EntityRegistry(entries)
        device_registry = DeviceRegistry(device)
        integration.er.async_get = lambda hass: entity_registry
        integration.dr.async_get = lambda hass: device_registry
        integration.er.async_entries_for_device = (
            lambda registry, device_id: list(registry.entries)
        )

        await integration._async_cleanup_inactive_devices(
            hass=object(),
            entry=SimpleNamespace(entry_id="entry-123"),
            inactive_suffixes={"wtc_experimental"},
        )

        self.assertEqual(entity_registry.removed, [])
        self.assertEqual(device_registry.removed, [])


if __name__ == "__main__":
    unittest.main()
