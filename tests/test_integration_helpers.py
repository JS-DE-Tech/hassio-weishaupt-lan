"""Unit tests for setup-time experimental probing and cleanup helpers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
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
sensors = load_module("custom_components.weishaupt_wtc_lan.sensors", PACKAGE_ROOT / "sensors.py")
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


class AdaptivePowerClient:
    """Fake client for adaptive WTC power probing."""

    def __init__(self, supported_vs: set[int]) -> None:
        self.supported_vs = supported_vs
        self.calls: list[int] = []

    async def read_parameters(self, params: list[dict]) -> dict:
        param = params[0]
        self.calls.append(param["vs"])
        if param["vs"] in self.supported_vs:
            return {
                param["key"]: {
                    "value_int": 0,
                    "value_hex": "00" * param["vs"],
                }
            }
        return {}


class NetworkClient:
    """Fake client for network diagnostics probing."""

    def __init__(self) -> None:
        self.params: list[dict] = []

    async def read_parameters(self, params: list[dict]) -> dict:
        self.params = params
        return {
            param["key"]: {"value_int": 0xC0A8012A, "value_hex": "c0a8012a"}
            for param in params
            if param["key"] == "network_ip_address"
        }

    async def read_string_parameter(self, *args, **kwargs):
        return None


class EntityRegistry:
    """Minimal entity registry."""

    def __init__(self, entries: list[SimpleNamespace]) -> None:
        self.entries = entries
        self.removed: list[str] = []
        self.updated: list[tuple[str, dict]] = []

    def async_remove(self, entity_id: str) -> None:
        self.removed.append(entity_id)
        self.entries = [entry for entry in self.entries if entry.entity_id != entity_id]

    def async_get_entity_id(self, domain: str, platform: str, unique_id: str):
        for entry in self.entries:
            if (
                getattr(entry, "domain", domain) == domain
                and getattr(entry, "platform", platform) == platform
                and getattr(entry, "unique_id", None) == unique_id
            ):
                return entry.entity_id
        return None

    def async_get(self, entity_id: str):
        for entry in self.entries:
            if entry.entity_id == entity_id:
                return entry
        return None

    def async_update_entity(self, entity_id: str, **kwargs) -> None:
        self.updated.append((entity_id, kwargs))
        entry = self.async_get(entity_id)
        if entry is not None and "disabled_by" in kwargs:
            entry.disabled_by = kwargs["disabled_by"]


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

    async def test_adaptive_wtc_power_keeps_vs4_zero_when_supported(self) -> None:
        """Adaptive WTC power probing should preserve raw zero for VS=4."""
        sensor_def = next(
            item
            for item in sensors.WTC_SENSORS
            if item.key == "wtc_waermeleistung_vpt"
        )
        client = AdaptivePowerClient({4})

        result = await integration._async_probe_wtc_power_definition(
            client,
            sensor_def,
        )

        self.assertEqual(result.vs, 4)
        self.assertEqual(client.calls, [4])

    async def test_adaptive_wtc_power_falls_back_to_vs2(self) -> None:
        """Adaptive WTC power probing should try VS=2 after VS=4 errors."""
        sensor_def = next(
            item
            for item in sensors.WTC_SENSORS
            if item.key == "wtc_waermeleistung_vpt"
        )
        client = AdaptivePowerClient({2})

        result = await integration._async_probe_wtc_power_definition(
            client,
            sensor_def,
        )

        self.assertEqual(result.vs, 2)
        self.assertEqual(client.calls, [4, 2])

    async def test_network_probe_skips_unsupported_hostname(self) -> None:
        """Network probing should keep numeric values when hostname is unsupported."""
        client = NetworkClient()
        supported, static_data = await integration._async_probe_network_sensors(
            client
        )

        self.assertEqual({item.key for item in supported}, {"network_ip_address"})
        self.assertEqual(static_data["network_ip_address"]["value_int"], 0xC0A8012A)
        self.assertTrue(all(param["key"] != "network_hostname" for param in client.params))

    async def test_network_static_data_is_not_polled_by_coordinator(self) -> None:
        """Network definitions should remain static and out of refresh batches."""
        network_def = next(
            item for item in sensors.NETWORK_SENSORS if item.key == "network_ip_address"
        )
        coordinator = integration.WeishauptDataUpdateCoordinator(
            hass=object(),
            client=FakeClient(set()),
            sensor_definitions=[network_def],
            static_data={
                "network_ip_address": {
                    "value_int": 0x0A6401E6,
                    "value_hex": "0a6401e6",
                }
            },
        )

        data = await coordinator._async_update_data()

        self.assertEqual(data["network_ip_address"]["value_int"], 0x0A6401E6)
        self.assertEqual(coordinator.client.params, [])

    async def test_snapshot_export_writes_json_and_csv_without_credentials(self) -> None:
        """Snapshot export should write local files without credentials."""
        sensor_def = next(
            item
            for item in sensors.WTC_SENSORS
            if item.key == "wtc_brennerstarts_gesamt"
        )
        coordinator = SimpleNamespace(
            data={sensor_def.key: {"value_int": 7, "value_hex": "0007"}},
            sensor_definitions=[sensor_def],
            experimental_wtc_registers=[],
            extended_experimental_wtc_registers=[],
        )
        entry = SimpleNamespace(
            entry_id="entry-123",
            data={
                "host": "wem-sg.local",
                "username": "admin",
                "password": "Admin123",
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = SimpleNamespace(
                config=SimpleNamespace(
                    path=lambda *parts: str(Path(tmpdir, *parts))
                )
            )

            paths = await integration._async_export_experimental_snapshot(
                hass,
                entry,
                coordinator,
            )

            json_text = Path(paths["json_path"]).read_text(encoding="utf-8")
            csv_text = Path(paths["csv_path"]).read_text(encoding="utf-8")
            payload = json.loads(json_text)
            self.assertEqual(payload["host_identifier"], "wem-sg.local")
            self.assertIn("wtc_brennerstarts_gesamt", json_text)
            self.assertIn("wtc_brennerstarts_gesamt", csv_text)
            self.assertNotIn("Admin123", json_text + csv_text)

    async def test_local_metadata_export_writes_systable_and_summary_without_credentials(self) -> None:
        """Metadata export should save raw metadata and a credential-free summary."""
        class MetadataClient:
            async def fetch_systable_csv(self) -> str:
                return "name;mi;mx\nPlattenwaermetauscher;0x02;0x00\n"

        coordinator = SimpleNamespace(
            client=MetadataClient(),
            heating_circuit_names={1: "Plattenwaermetauscher"},
        )
        entry = SimpleNamespace(
            entry_id="entry-123",
            data={
                "host": "wem-sg.local",
                "username": "admin",
                "password": "Admin123",
                "detected_heating_circuit_names": {"1": "Persisted HK1"},
            },
            options={},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = SimpleNamespace(
                config=SimpleNamespace(
                    path=lambda *parts: str(Path(tmpdir, *parts))
                )
            )

            paths = await integration._async_export_local_metadata(
                hass,
                entry,
                coordinator,
            )

            self.assertIn("systable_csv_path", paths)
            summary_text = Path(paths["summary_json_path"]).read_text(encoding="utf-8")
            self.assertIn("Plattenwaermetauscher", summary_text)
            self.assertNotIn("Admin123", summary_text)

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

    async def test_reenable_only_integration_disabled_default_entities(self) -> None:
        """Default-enabled diagnostics should be re-enabled only for integration-disabled entries."""
        entries = [
            SimpleNamespace(
                entity_id="sensor.date",
                unique_id="entry-123_sg_device_date",
                config_entry_id="entry-123",
                domain="sensor",
                platform="weishaupt_wtc_lan",
                disabled_by="integration",
            ),
            SimpleNamespace(
                entity_id="sensor.user_disabled",
                unique_id="entry-123_network_ip_address",
                config_entry_id="entry-123",
                domain="sensor",
                platform="weishaupt_wtc_lan",
                disabled_by="user",
            ),
        ]
        entity_registry = EntityRegistry(entries)
        integration.er.async_get = lambda hass: entity_registry

        await integration._async_reenable_integration_default_entities(
            object(),
            SimpleNamespace(entry_id="entry-123"),
            {"sg_device_date", "network_ip_address"},
        )

        self.assertEqual(entity_registry.updated, [("sensor.date", {"disabled_by": None})])
        self.assertIsNone(entries[0].disabled_by)
        self.assertEqual(entries[1].disabled_by, "user")

    async def test_cleanup_stale_readonly_hk_setpoint_sensors_only(self) -> None:
        """Stale HK2/HK3 read-only setpoint sensors should be removed safely."""
        entries = [
            SimpleNamespace(
                entity_id="sensor.hk2_duplicate",
                unique_id="entry-123_hk_betriebsart_vorgabe",
                config_entry_id="entry-123",
                domain="sensor",
                platform="weishaupt_wtc_lan",
            ),
            SimpleNamespace(
                entity_id="select.hk2",
                unique_id="entry-123_hk_betriebsart_vorgabe_select",
                config_entry_id="entry-123",
                domain="select",
                platform="weishaupt_wtc_lan",
            ),
            SimpleNamespace(
                entity_id="sensor.other",
                unique_id="entry-123_hk_betriebsart_aktuell",
                config_entry_id="entry-123",
                domain="sensor",
                platform="weishaupt_wtc_lan",
            ),
        ]
        entity_registry = EntityRegistry(entries)
        integration.er.async_get = lambda hass: entity_registry

        await integration._async_cleanup_stale_readonly_operating_mode_sensors(
            object(),
            SimpleNamespace(entry_id="entry-123"),
        )

        self.assertEqual(entity_registry.removed, ["sensor.hk2_duplicate"])


if __name__ == "__main__":
    unittest.main()
