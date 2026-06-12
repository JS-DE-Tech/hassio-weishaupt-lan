"""Unit tests for setup-time experimental probing and cleanup helpers."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from datetime import datetime, timedelta, timezone
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
        self.data = None
        self.update_interval = kwargs.get("update_interval")
        self.refresh_calls = 0

    def async_set_updated_data(self, data) -> None:
        """Store updated coordinator data."""
        self.data = data

    async def async_request_refresh(self) -> None:
        """Record refresh requests."""
        self.refresh_calls += 1


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
coordinator_module = sys.modules["custom_components.weishaupt_wtc_lan.coordinator"]


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

    def __init__(
        self,
        *,
        string_values: dict[tuple[int, int, int, int, int], str] | None = None,
        mac_components: list[int] | None = None,
    ) -> None:
        self.params: list[dict] = []
        self.param_batches: list[list[dict]] = []
        self.string_calls: list[dict] = []
        self.string_values = string_values or {}
        self.mac_components = mac_components

    async def read_parameters(self, params: list[dict]) -> dict:
        self.params = params
        self.param_batches.append(params)
        mac_by_key = {
            f"network_mac_component_{index}": value
            for index, value in enumerate(self.mac_components or [], start=1)
        }
        return {
            param["key"]: {
                "value_int": (
                    3
                    if param["key"] == "network_ip_mode"
                    else mac_by_key.get(param["key"], 0xC0A8012A)
                ),
                "value_hex": (
                    "03"
                    if param["key"] == "network_ip_mode"
                    else f"{mac_by_key[param['key']]:04x}"
                    if param["key"] in mac_by_key
                    else "c0a8012a"
                ),
            }
            for param in params
            if param["key"]
            in {
                "network_ip_mode",
                "network_ip_address",
                "network_subnet_mask",
                "network_gateway",
                "network_dns_server",
                *mac_by_key.keys(),
            }
        }

    async def read_string_parameter(self, *args, **kwargs):
        self.string_calls.append(kwargs)
        lookup = (
            kwargs["mi"],
            kwargs["mx"],
            kwargs["ox"],
            kwargs["os_val"],
            kwargs["vs"],
        )
        value = self.string_values.get(lookup)
        if not value:
            return None
        return {
            "value_int": 0,
            "value_hex": value.encode("utf-8").hex(),
            "value_string": value,
        }


class WriteQueueClient:
    """Fake client recording serialized queued writes."""

    def __init__(self) -> None:
        self.writes: list[dict] = []
        self.active_writes = 0
        self.max_active_writes = 0
        self.params: list[dict] = []

    async def write_parameter(self, **kwargs) -> bool:
        self.active_writes += 1
        self.max_active_writes = max(self.max_active_writes, self.active_writes)
        self.writes.append(kwargs)
        await asyncio.sleep(0)
        self.active_writes -= 1
        return True

    async def read_parameters(self, params: list[dict]) -> dict:
        self.params = params
        return {}


class SequenceReadClient:
    """Fake client returning one dynamic read result per coordinator poll."""

    def __init__(self, responses: list[tuple[dict, int]]) -> None:
        self.responses = list(responses)
        self.last_read_failed_batches = 0
        self.params: list[dict] = []

    async def read_parameters(self, params: list[dict]) -> dict:
        self.params = params
        if not self.responses:
            self.last_read_failed_batches = 0
            return {}
        response, failed_batches = self.responses.pop(0)
        self.last_read_failed_batches = failed_batches
        return response


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


def sensor_definition_by_key(key: str):
    """Return a sensor definition by key."""
    return next(item for item in sensors.ALL_SENSORS if item.key == key)


class IntegrationHelperTests(unittest.IsolatedAsyncioTestCase):
    """Test setup helper behavior."""

    def setUp(self) -> None:
        """Use short write timings for tests."""
        self._original_write_debounce = coordinator_module.WRITE_DEBOUNCE_SECONDS
        self._original_post_write_settle = coordinator_module.POST_WRITE_SETTLE_SECONDS
        coordinator_module.WRITE_DEBOUNCE_SECONDS = 0.01
        coordinator_module.POST_WRITE_SETTLE_SECONDS = 0.03

    def tearDown(self) -> None:
        """Restore production write timings."""
        coordinator_module.WRITE_DEBOUNCE_SECONDS = self._original_write_debounce
        coordinator_module.POST_WRITE_SETTLE_SECONDS = self._original_post_write_settle

    async def test_quick_repeated_writes_to_same_register_are_coalesced(self) -> None:
        """Only the newest pending value for the same register should be sent."""
        client = WriteQueueClient()
        sensor_def = sensor_definition_by_key("sg_systembetriebsart")
        coordinator = integration.WeishauptDataUpdateCoordinator(
            hass=object(),
            client=client,
            sensor_definitions=[sensor_def],
        )

        await coordinator.async_enqueue_write(sensor_def, 1)
        await coordinator.async_enqueue_write(sensor_def, 3)
        await asyncio.sleep(0.05)

        self.assertEqual(len(client.writes), 1)
        self.assertEqual(client.writes[0]["value_int"], 3)
        self.assertEqual(coordinator.data[sensor_def.key]["value_int"], 3)

    async def test_different_register_writes_are_sent_serially_in_order(self) -> None:
        """Different target registers should keep insertion order and not overlap."""
        client = WriteQueueClient()
        first = sensor_definition_by_key("sg_systembetriebsart")
        second = sensor_definition_by_key("sg_betriebsart_hk1_vorgabe")
        coordinator = integration.WeishauptDataUpdateCoordinator(
            hass=object(),
            client=client,
            sensor_definitions=[first, second],
        )

        await coordinator.async_enqueue_write(first, 1)
        await coordinator.async_enqueue_write(second, 2)
        await asyncio.sleep(0.05)

        self.assertEqual(
            [item["ox"] for item in client.writes],
            [first.ox, second.ox],
        )
        self.assertEqual(client.max_active_writes, 1)

    async def test_write_settle_requests_one_delayed_refresh(self) -> None:
        """Writes should not request an immediate full refresh."""
        client = WriteQueueClient()
        sensor_def = sensor_definition_by_key("sg_systembetriebsart")
        coordinator = integration.WeishauptDataUpdateCoordinator(
            hass=object(),
            client=client,
            sensor_definitions=[sensor_def],
        )

        await coordinator.async_enqueue_write(sensor_def, 1)
        await asyncio.sleep(0.02)
        self.assertEqual(coordinator.refresh_calls, 0)

        await asyncio.sleep(0.05)
        self.assertEqual(coordinator.refresh_calls, 1)

    async def test_new_write_resets_post_write_settle_timer(self) -> None:
        """A later write should cancel the earlier delayed refresh timer."""
        client = WriteQueueClient()
        first = sensor_definition_by_key("sg_systembetriebsart")
        second = sensor_definition_by_key("sg_betriebsart_hk1_vorgabe")
        coordinator = integration.WeishauptDataUpdateCoordinator(
            hass=object(),
            client=client,
            sensor_definitions=[first, second],
        )

        await coordinator.async_enqueue_write(first, 1)
        await asyncio.sleep(0.025)
        await coordinator.async_enqueue_write(second, 2)
        await asyncio.sleep(0.02)
        self.assertEqual(coordinator.refresh_calls, 0)

        await asyncio.sleep(0.05)
        self.assertEqual(coordinator.refresh_calls, 1)

    async def test_polling_is_skipped_while_writes_pending_or_settling(self) -> None:
        """Ordinary polling should return cached data during write protection windows."""
        coordinator_module.POST_WRITE_SETTLE_SECONDS = 0.2
        client = WriteQueueClient()
        sensor_def = sensor_definition_by_key("sg_systembetriebsart")
        coordinator = integration.WeishauptDataUpdateCoordinator(
            hass=object(),
            client=client,
            sensor_definitions=[sensor_def],
            static_data={"network_ip_address": {"value_int": 0x0A000001}},
        )
        coordinator.data = {"cached": {"value_int": 1}}

        await coordinator.async_enqueue_write(sensor_def, 1)
        pending_data = await coordinator._async_update_data()
        for _ in range(10):
            if sensor_def.key in (coordinator.data or {}):
                break
            await asyncio.sleep(0.01)
        settling_data = await coordinator._async_update_data()

        self.assertEqual(client.params, [])
        self.assertEqual(pending_data["cached"]["value_int"], 1)
        self.assertEqual(settling_data[sensor_def.key]["value_int"], 1)

    async def test_acknowledged_target_value_is_reflected_without_mirrors(self) -> None:
        """ACKed target values should update only the written target key."""
        client = WriteQueueClient()
        target = sensor_definition_by_key("sg_systembetriebsart")
        mirror = sensor_definition_by_key("sg_systembetriebsart_aktuell")
        coordinator = integration.WeishauptDataUpdateCoordinator(
            hass=object(),
            client=client,
            sensor_definitions=[target, mirror],
        )

        await coordinator.async_enqueue_write(target, 3)
        await asyncio.sleep(0.05)

        self.assertEqual(coordinator.data[target.key]["value_int"], 3)
        self.assertNotIn(mirror.key, coordinator.data)

    async def test_previous_dynamic_values_survive_failed_later_batch(self) -> None:
        """A later partial read failure should retain previous valid dynamic values."""
        sensor_def = sensor_definition_by_key("sg_systembetriebsart")
        client = SequenceReadClient(
            [
                (
                    {
                        sensor_def.key: {
                            "value_int": 2,
                            "value_hex": "02",
                        }
                    },
                    0,
                ),
                ({}, 1),
            ]
        )
        coordinator = integration.WeishauptDataUpdateCoordinator(
            hass=object(),
            client=client,
            sensor_definitions=[sensor_def],
        )

        first = await coordinator._async_update_data()
        second = await coordinator._async_update_data()

        self.assertEqual(first[sensor_def.key]["value_int"], 2)
        self.assertEqual(second[sensor_def.key]["value_int"], 2)

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

    async def test_network_probe_skips_unsupported_optional_strings(self) -> None:
        """Network probing should keep numeric values when optional strings fail."""
        client = NetworkClient()
        supported, static_data = await integration._async_probe_network_sensors(
            client
        )

        self.assertEqual(
            {item.key for item in supported},
            {
                "network_ip_mode",
                "network_ip_address",
                "network_subnet_mask",
                "network_gateway",
                "network_dns_server",
            },
        )
        self.assertEqual(static_data["network_ip_address"]["value_int"], 0xC0A8012A)
        self.assertNotIn("network_hostname", static_data)
        self.assertNotIn("network_certificate_cn", static_data)
        self.assertNotIn("network_mac_address", static_data)

    async def test_network_probe_uses_confirmed_readonly_queries(self) -> None:
        """Network probing should use confirmed GET, GETS, and MAC component queries."""
        client = NetworkClient(
            string_values={
                (0x06, 0x00, 0x250E, 0x00, 16): "GATEWAY0",
                (0x06, 0x00, 0x2511, 0x00, 50): "wem.example.local",
            },
            mac_components=[0x00, 0x11, 0x22, 0xAA, 0xBB, 0xCC],
        )

        supported, static_data = await integration._async_probe_network_sensors(
            client
        )

        numeric_queries = {
            (param["key"], param["mi"], param["mx"], param["ox"], param["os"], param["vs"])
            for param in client.param_batches[0]
        }
        self.assertEqual(
            numeric_queries,
            {
                ("network_ip_mode", 0x06, 0x00, 0x2507, 0x00, 1),
                ("network_ip_address", 0x06, 0x00, 0x2508, 0x00, 4),
                ("network_subnet_mask", 0x06, 0x00, 0x2509, 0x00, 4),
                ("network_gateway", 0x06, 0x00, 0x250A, 0x00, 4),
                ("network_dns_server", 0x06, 0x00, 0x250B, 0x00, 4),
            },
        )
        self.assertEqual(
            {
                (call["mi"], call["mx"], call["ox"], call["os_val"], call["vs"])
                for call in client.string_calls
            },
            {
                (0x06, 0x00, 0x250E, 0x00, 16),
                (0x06, 0x00, 0x2511, 0x00, 50),
            },
        )
        self.assertEqual(
            {
                (param["key"], param["mi"], param["mx"], param["ox"], param["os"], param["vs"])
                for param in client.param_batches[1]
            },
            {
                (f"network_mac_component_{index}", 0x06, 0x00, 0x250C, index, 2)
                for index in range(1, 7)
            },
        )
        self.assertEqual(static_data["network_hostname"]["value_string"], "GATEWAY0")
        self.assertEqual(
            static_data["network_certificate_cn"]["value_string"],
            "wem.example.local",
        )
        self.assertEqual(
            static_data["network_mac_address"]["value_string"],
            "00-11-22-AA-BB-CC",
        )
        self.assertIn("network_mac_address", {item.key for item in supported})
        self.assertLessEqual(max(len(batch) for batch in client.param_batches), 6)

    async def test_network_probe_skips_empty_device_name(self) -> None:
        """Empty device-name strings should skip the optional diagnostic safely."""
        client = NetworkClient(
            string_values={(0x06, 0x00, 0x250E, 0x00, 16): "   "},
        )

        supported, static_data = await integration._async_probe_network_sensors(
            client
        )

        self.assertNotIn("network_hostname", static_data)
        self.assertNotIn("network_hostname", {item.key for item in supported})

    async def test_network_probe_skips_missing_mac_component(self) -> None:
        """Missing MAC components should skip the derived MAC entity safely."""
        client = NetworkClient(mac_components=[0x00, 0x11, 0x22, 0xAA, 0xBB])

        supported, static_data = await integration._async_probe_network_sensors(
            client
        )

        self.assertNotIn("network_mac_address", static_data)
        self.assertNotIn("network_mac_address", {item.key for item in supported})

    async def test_network_probe_skips_invalid_mac_component(self) -> None:
        """Out-of-range MAC components should skip the derived MAC entity safely."""
        client = NetworkClient(mac_components=[0x00, 0x11, 0x22, 0xAA, 0xBB, 0x100])

        supported, static_data = await integration._async_probe_network_sensors(
            client
        )

        self.assertNotIn("network_mac_address", static_data)
        self.assertNotIn("network_mac_address", {item.key for item in supported})

    async def test_network_static_data_is_not_polled_by_coordinator(self) -> None:
        """Network definitions should remain static and out of refresh batches."""
        network_defs = [
            item for item in sensors.NETWORK_SENSORS
            if item.key in {"network_ip_address", "network_mac_address"}
        ]
        coordinator = integration.WeishauptDataUpdateCoordinator(
            hass=object(),
            client=FakeClient(set()),
            sensor_definitions=network_defs,
            static_data={
                "network_ip_address": {
                    "value_int": 0x0A6401E6,
                    "value_hex": "0a6401e6",
                },
                "network_mac_address": {
                    "value_int": 0,
                    "value_hex": "001122aabbcc",
                    "value_string": "00-11-22-AA-BB-CC",
                },
            },
        )

        data = await coordinator._async_update_data()

        self.assertEqual(data["network_ip_address"]["value_int"], 0x0A6401E6)
        self.assertEqual(
            data["network_mac_address"]["value_string"],
            "00-11-22-AA-BB-CC",
        )
        self.assertEqual(coordinator.client.params, [])

    async def test_network_refresh_retains_cached_mac_on_later_failure(self) -> None:
        """Later MAC refresh failures should keep the last valid cached value."""
        async def empty_network_refresh() -> dict:
            return {}

        coordinator = integration.WeishauptDataUpdateCoordinator(
            hass=object(),
            client=FakeClient(set()),
            sensor_definitions=[],
            static_data={
                "network_mac_address": {
                    "value_int": 0,
                    "value_hex": "001122aabbcc",
                    "value_string": "00-11-22-AA-BB-CC",
                },
            },
            network_refresh_callback=empty_network_refresh,
        )
        coordinator._last_network_refresh = datetime(2026, 6, 12, tzinfo=timezone.utc)

        refreshed = await coordinator.async_refresh_network_diagnostics(
            now=datetime(2026, 6, 12, 0, 11, tzinfo=timezone.utc)
        )

        self.assertFalse(refreshed)
        self.assertEqual(
            coordinator.static_data["network_mac_address"]["value_string"],
            "00-11-22-AA-BB-CC",
        )

    async def test_network_refresh_is_throttled_for_regular_updates(self) -> None:
        """Network refresh should run at most once per ten minutes."""
        calls = 0

        async def network_refresh() -> dict:
            nonlocal calls
            calls += 1
            return {"network_dns_server": {"value_int": 0x0A640001, "value_hex": "0a640001"}}

        coordinator = integration.WeishauptDataUpdateCoordinator(
            hass=object(),
            client=FakeClient(set()),
            sensor_definitions=[],
            static_data={},
            network_refresh_callback=network_refresh,
        )
        coordinator._last_network_refresh = datetime.now(timezone.utc)
        await coordinator._async_update_data()
        self.assertEqual(calls, 0)
        self.assertEqual(coordinator.client.params, [])

        coordinator._last_network_refresh = datetime(2026, 6, 12, tzinfo=timezone.utc)

        skipped = await coordinator.async_refresh_network_diagnostics(
            now=datetime(2026, 6, 12, 0, 9, 59, tzinfo=timezone.utc)
        )
        refreshed = await coordinator.async_refresh_network_diagnostics(
            now=datetime(2026, 6, 12, 0, 10, 1, tzinfo=timezone.utc)
        )

        self.assertFalse(skipped)
        self.assertTrue(refreshed)
        self.assertEqual(calls, 1)
        self.assertIn("network_dns_server", coordinator.static_data)

    async def test_network_refresh_runs_on_setup_and_reload_probe(self) -> None:
        """Setup/reload probes should immediately read network diagnostics."""
        setup_client = NetworkClient()
        reload_client = NetworkClient()

        await integration._async_probe_network_sensors(setup_client)
        await integration._async_probe_network_sensors(reload_client)

        self.assertEqual(len(setup_client.param_batches), 2)
        self.assertEqual(len(reload_client.param_batches), 2)

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
