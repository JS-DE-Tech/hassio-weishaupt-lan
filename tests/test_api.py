"""Unit tests for Weishaupt API batching and response isolation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
import asyncio

REAL_ASYNCIO_SLEEP = asyncio.sleep


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "custom_components" / "weishaupt_wtc_lan"


aiohttp_stub = types.ModuleType("aiohttp")


class ClientConnectorError(Exception):
    """Minimal aiohttp connector error."""


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
    """Minimal aiohttp session stub."""

    closed = False

    async def close(self) -> None:
        """Close the stub session."""


aiohttp_stub.ClientConnectorError = ClientConnectorError
aiohttp_stub.BasicAuth = BasicAuth
aiohttp_stub.ClientTimeout = ClientTimeout
aiohttp_stub.ClientSession = ClientSession
sys.modules.setdefault("aiohttp", aiohttp_stub)


def load_module(module_name: str, file_path: Path):
    """Load a package module from a file."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


custom_components_pkg = types.ModuleType("custom_components")
custom_components_pkg.__path__ = [str(REPO_ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components_pkg)

integration_pkg = types.ModuleType("custom_components.weishaupt_wtc_lan")
integration_pkg.__path__ = [str(PACKAGE_ROOT)]
sys.modules.setdefault("custom_components.weishaupt_wtc_lan", integration_pkg)

load_module("custom_components.weishaupt_wtc_lan.const", PACKAGE_ROOT / "const.py")
api = load_module("custom_components.weishaupt_wtc_lan.api", PACKAGE_ROOT / "api.py")


class SequenceResponseClient(api.WeishauptApiClient):
    """API client test double returning one response per request."""

    def __init__(self, responses: list[dict | None]) -> None:
        super().__init__("wem-sg", "admin", "Admin123")
        self.responses = list(responses)
        self.payloads: list[dict] = []

    async def _post(self, payload: dict) -> dict | None:
        """Capture the payload and return the next configured response."""
        self.payloads.append(payload)
        return self.responses.pop(0)


class FakeJsonResponse:
    """Minimal aiohttp response object."""

    status = 200

    async def json(self, content_type=None):
        """Return a valid CanApiJson response."""
        return {"CAPI": {"NN": 0}}


class FakePostContext:
    """Async context manager recording concurrent request attempts."""

    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        self.session.active_requests += 1
        self.session.max_active_requests = max(
            self.session.max_active_requests,
            self.session.active_requests,
        )
        await REAL_ASYNCIO_SLEEP(0.01)
        return FakeJsonResponse()

    async def __aexit__(self, exc_type, exc, tb):
        self.session.active_requests -= 1
        return False


class FakeSession:
    """Minimal aiohttp session recording post calls."""

    closed = False

    def __init__(self) -> None:
        self.active_requests = 0
        self.max_active_requests = 0
        self.posts = 0

    def post(self, *args, **kwargs):
        """Return a fake post context."""
        self.posts += 1
        return FakePostContext(self)


def capi_batch_response(vgs: list[str | None]) -> dict:
    """Build a CanApiJson batch response."""
    capi = {"NN": len(vgs)}
    for index, frame in enumerate(vgs, start=1):
        if frame is not None:
            capi[f"N{index:02d}"] = {"VG": frame}
    return {"CAPI": capi}


def vg_with_value(
    cmd: int, mi: int, mx: int, ox: int, os_val: int, vs: int, value: int
) -> str:
    """Build a response VG frame with value bytes."""
    return (
        f"{cmd:02x}{mi:02x}{mx:02x}{ox:04x}{os_val:02x}"
        f"{vs:04x}{value:0{vs * 2}x}"
    )


def params(count: int) -> list[dict[str, int | str]]:
    """Return synthetic read parameters."""
    return [
        {
            "key": f"key_{index}",
            "mi": 0x09,
            "mx": 0x01,
            "ox": 0x2600 + index,
            "os": 0x02,
            "vs": 2,
        }
        for index in range(count)
    ]


class ApiClientTests(unittest.IsolatedAsyncioTestCase):
    """Test CanApiJson read behavior."""

    async def test_post_calls_are_serialized(self) -> None:
        """Concurrent _post calls should run one HTTP request at a time."""
        session = FakeSession()
        client = api.WeishauptApiClient("wem-sg", "admin", "Admin123", session=session)
        original_gap = api.MIN_REQUEST_GAP_SECONDS
        api.MIN_REQUEST_GAP_SECONDS = 0
        try:
            await asyncio.gather(client._post({"one": 1}), client._post({"two": 2}))
        finally:
            api.MIN_REQUEST_GAP_SECONDS = original_gap

        self.assertEqual(session.posts, 2)
        self.assertEqual(session.max_active_requests, 1)

    async def test_post_respects_minimum_request_gap(self) -> None:
        """A request should wait for the remaining configured inter-request gap."""
        session = FakeSession()
        client = api.WeishauptApiClient("wem-sg", "admin", "Admin123", session=session)
        original_gap = api.MIN_REQUEST_GAP_SECONDS
        api.MIN_REQUEST_GAP_SECONDS = 0.02
        client._last_request_completed = api.time.monotonic() - 0.005
        sleeps: list[float] = []
        original_sleep = api.asyncio.sleep

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        api.asyncio.sleep = fake_sleep
        try:
            await client._post({"ID": "12345678"})
        finally:
            api.asyncio.sleep = original_sleep
            api.MIN_REQUEST_GAP_SECONDS = original_gap

        self.assertEqual(len(sleeps), 1)
        self.assertGreater(sleeps[0], 0)
        self.assertLessEqual(sleeps[0], 0.02)

    async def test_read_parameters_splits_batches_at_six_dense_frames(self) -> None:
        """Read batches should contain no more than six densely numbered frames."""
        requested = params(7)
        client = SequenceResponseClient(
            [
                capi_batch_response(
                    [
                        vg_with_value(
                            api.CMD_RESPONSE,
                            int(param["mi"]),
                            int(param["mx"]),
                            int(param["ox"]),
                            int(param["os"]),
                            int(param["vs"]),
                            2,
                        )
                        for param in requested[:6]
                    ]
                ),
                capi_batch_response(
                    [
                        vg_with_value(
                            api.CMD_RESPONSE,
                            int(requested[6]["mi"]),
                            int(requested[6]["mx"]),
                            int(requested[6]["ox"]),
                            int(requested[6]["os"]),
                            int(requested[6]["vs"]),
                            2,
                        )
                    ]
                ),
            ]
        )

        result = await client.read_parameters(requested)

        self.assertEqual(len(result), 7)
        self.assertEqual(client.payloads[0]["CAPI"]["NN"], 6)
        self.assertEqual(client.payloads[1]["CAPI"]["NN"], 1)
        self.assertEqual(
            [key for key in client.payloads[0]["CAPI"] if key.startswith("N")],
            ["NN", "N01", "N02", "N03", "N04", "N05", "N06"],
        )
        self.assertEqual(
            [key for key in client.payloads[1]["CAPI"] if key.startswith("N")],
            ["NN", "N01"],
        )

    async def test_cmd_error_does_not_discard_valid_frames_or_zero(self) -> None:
        """One CMD_ERROR should not discard valid responses in the same batch."""
        requested = params(6)
        response_frames = [
            vg_with_value(api.CMD_RESPONSE, 0x09, 0x01, 0x2600, 0x02, 2, 149),
            vg_with_value(api.CMD_ERROR, 0x09, 0x01, 0x2601, 0x02, 2, 0),
            vg_with_value(api.CMD_RESPONSE, 0x09, 0x01, 0x2602, 0x02, 2, 0),
            vg_with_value(api.CMD_RESPONSE, 0x09, 0x01, 0x2603, 0x02, 2, 597),
            vg_with_value(api.CMD_RESPONSE, 0x09, 0x01, 0x2604, 0x02, 2, 1),
            vg_with_value(api.CMD_RESPONSE, 0x09, 0x01, 0x2605, 0x02, 2, 2),
        ]
        client = SequenceResponseClient([capi_batch_response(response_frames)])

        result = await client.read_parameters(requested)

        self.assertNotIn("key_1", result)
        self.assertEqual(result["key_0"]["value_int"], 149)
        self.assertEqual(result["key_2"]["value_int"], 0)
        self.assertEqual(result["key_3"]["value_int"], 597)

    async def test_read_string_parameter_decodes_supported_device_name(self) -> None:
        """String read should decode a supported NUL-terminated device name."""
        value_hex = "57454d2d5347202000" + ("00" * 7)
        client = SequenceResponseClient(
            [
                capi_batch_response(
                    [
                        (
                            f"{api.CMD_RESPONSE_STRING:02x}0600250e00"
                            f"{16:04x}{value_hex}"
                        )
                    ]
                )
            ]
        )

        result = await client.read_string_parameter(0x06, 0x00, 0x250E, 0x00, 16)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["value_string"], "WEM-SG")
        self.assertEqual(client.payloads[0]["CAPI"]["NN"], 1)
        self.assertIn(f"{api.CMD_GET_STRING:02x}", client.payloads[0]["CAPI"]["N01"]["VG"][:2])

    async def test_read_string_parameter_returns_none_when_unsupported(self) -> None:
        """Unsupported string reads should not fail setup."""
        client = SequenceResponseClient(
            [
                capi_batch_response(
                    [vg_with_value(api.CMD_ERROR, 0x06, 0x00, 0x250E, 0x00, 16, 0)]
                )
            ]
        )

        result = await client.read_string_parameter(0x06, 0x00, 0x250E, 0x00, 16)

        self.assertIsNone(result)

    async def test_write_parameter_rejects_ack_address_mismatch(self) -> None:
        """Write ACK validation should reject mismatched register addresses."""
        client = SequenceResponseClient(
            [
                capi_batch_response(
                    [vg_with_value(api.CMD_ACK, 0x02, 0x00, 0x2534, 0x02, 1, 3)]
                )
            ]
        )

        success = await client.write_parameter(
            mi=0x02,
            mx=0x00,
            ox=0x2533,
            os_val=0x02,
            vs=1,
            value_int=3,
        )

        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
