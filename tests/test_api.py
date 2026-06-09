"""Unit tests for Weishaupt API client edge cases."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "custom_components" / "weishaupt_wtc"


aiohttp_stub = types.ModuleType("aiohttp")


class ClientConnectorError(Exception):
    """Minimal aiohttp exception stub used by the API client."""


class BasicAuth:
    """Minimal aiohttp auth stub."""

    def __init__(self, login: str, password: str) -> None:
        self.login = login
        self.password = password


class ClientTimeout:
    """Minimal aiohttp timeout stub."""

    def __init__(self, total: int | None = None) -> None:
        self.total = total


class ClientSession:
    """Minimal aiohttp session stub for type compatibility."""

    closed = False

    async def close(self) -> None:
        """Provide the interface used by the client close method."""


aiohttp_stub.ClientConnectorError = ClientConnectorError
aiohttp_stub.BasicAuth = BasicAuth
aiohttp_stub.ClientTimeout = ClientTimeout
aiohttp_stub.ClientSession = ClientSession
sys.modules.setdefault("aiohttp", aiohttp_stub)


def load_module(module_name: str, file_path: Path):
    """Load a module from file while preserving package-relative imports."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


custom_components_pkg = types.ModuleType("custom_components")
custom_components_pkg.__path__ = [str(REPO_ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components_pkg)

integration_pkg = types.ModuleType("custom_components.weishaupt_wtc")
integration_pkg.__path__ = [str(PACKAGE_ROOT)]
sys.modules.setdefault("custom_components.weishaupt_wtc", integration_pkg)

load_module("custom_components.weishaupt_wtc.const", PACKAGE_ROOT / "const.py")
api = load_module("custom_components.weishaupt_wtc.api", PACKAGE_ROOT / "api.py")


class EmptyResponseClient(api.WeishauptApiClient):
    """API client test double that always returns an empty device response."""

    async def _post(self, payload: dict) -> dict | None:
        """Return the empty response that triggered issue #2."""
        return None


class ResponseClient(api.WeishauptApiClient):
    """API client test double returning a configured response."""

    def __init__(self, response: dict | None) -> None:
        super().__init__("wem-sg", "admin", "Admin123")
        self.response = response
        self.payloads: list[dict] = []

    async def _post(self, payload: dict) -> dict | None:
        """Capture the payload and return the configured response."""
        self.payloads.append(payload)
        return self.response


def capi_response(vg: str) -> dict:
    """Build a minimal CanApiJson response."""
    return {"CAPI": {"N01": {"VG": vg}}}


def vg(cmd: int, mi: int, mx: int, ox: int, os_val: int, vs: int) -> str:
    """Build a minimal response VG without value bytes."""
    return f"{cmd:02x}{mi:02x}{mx:02x}{ox:04x}{os_val:02x}{vs:04x}"


class ApiClientTests(unittest.IsolatedAsyncioTestCase):
    """Test API client behavior for empty device responses."""

    async def test_test_connection_returns_false_for_empty_response(self) -> None:
        """Connection test should not crash on an empty response."""
        client = EmptyResponseClient("wem-sg", "admin", "Admin123")

        self.assertFalse(await client.test_connection())

    async def test_read_parameters_skips_empty_response(self) -> None:
        """Batch reads should warn and skip empty responses instead of failing."""
        client = EmptyResponseClient("wem-sg", "admin", "Admin123")
        params = [
            {
                "key": "sg_betriebsart_hk1",
                "mi": 0x02,
                "mx": 0x00,
                "ox": 0x2533,
                "os": 0x02,
                "vs": 0x01,
            }
        ]

        with self.assertLogs(
            "custom_components.weishaupt_wtc.api", level="WARNING"
        ) as logs:
            result = await client.read_parameters(params)

        self.assertEqual(result, {})
        self.assertTrue(
            any("Empty response from device" in entry for entry in logs.output)
        )

    async def test_has_heating_circuit_sends_hk2_mx(self) -> None:
        """HK2 discovery should probe MI=0x02/MX=0x01."""
        client = ResponseClient(
            capi_response(vg(api.CMD_RESPONSE, 0x02, 0x01, 0x2533, 0x02, 1))
        )

        self.assertTrue(await client.has_heating_circuit(0x01))

        sent_vg = client.payloads[0]["CAPI"]["N01"]["VG"]
        self.assertEqual(sent_vg[2:6], "0201")

    async def test_has_heating_circuit_sends_hk3_mx(self) -> None:
        """HK3 discovery should probe MI=0x02/MX=0x02."""
        client = ResponseClient(
            capi_response(vg(api.CMD_RESPONSE, 0x02, 0x02, 0x2533, 0x02, 1))
        )

        self.assertTrue(await client.has_heating_circuit(0x02))

        sent_vg = client.payloads[0]["CAPI"]["N01"]["VG"]
        self.assertEqual(sent_vg[2:6], "0202")

    async def test_write_parameter_accepts_matching_ack(self) -> None:
        """A matching CMD_ACK should be accepted as a successful write."""
        client = ResponseClient(
            capi_response(vg(api.CMD_ACK, 0x02, 0x01, 0x2533, 0x02, 1))
        )

        self.assertTrue(
            await client.write_parameter(0x02, 0x01, 0x2533, 0x02, 1, 6)
        )

    async def test_write_parameter_rejects_error(self) -> None:
        """CMD_ERROR should reject a write."""
        client = ResponseClient(
            capi_response(vg(api.CMD_ERROR, 0x02, 0x01, 0x2533, 0x02, 1))
        )

        self.assertFalse(
            await client.write_parameter(0x02, 0x01, 0x2533, 0x02, 1, 6)
        )

    async def test_write_parameter_rejects_response_instead_of_ack(self) -> None:
        """CMD_RESPONSE must not be accepted as a write confirmation."""
        client = ResponseClient(
            capi_response(vg(api.CMD_RESPONSE, 0x02, 0x01, 0x2533, 0x02, 1))
        )

        self.assertFalse(
            await client.write_parameter(0x02, 0x01, 0x2533, 0x02, 1, 6)
        )

    async def test_write_parameter_rejects_missing_response(self) -> None:
        """Missing CAPI/VG data should reject a write."""
        client = ResponseClient({"CAPI": {}})

        self.assertFalse(
            await client.write_parameter(0x02, 0x01, 0x2533, 0x02, 1, 6)
        )

    async def test_write_parameter_rejects_incomplete_response(self) -> None:
        """Incomplete VG data should reject a write."""
        client = ResponseClient(capi_response("040201"))

        self.assertFalse(
            await client.write_parameter(0x02, 0x01, 0x2533, 0x02, 1, 6)
        )


if __name__ == "__main__":
    unittest.main()
