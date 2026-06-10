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


def capi_response(vg: str) -> dict:
    """Build a minimal CanApiJson response."""
    return {"CAPI": {"N01": {"VG": vg}}}


def capi_batch_response(vgs: list[str | None]) -> dict:
    """Build a CanApiJson response with optional missing VG slots."""
    capi = {"NN": len(vgs)}
    for index, frame in enumerate(vgs, start=1):
        if frame is not None:
            capi[f"N{index:02d}"] = {"VG": frame}
    return {"CAPI": capi}


def vg(cmd: int, mi: int, mx: int, ox: int, os_val: int, vs: int) -> str:
    """Build a minimal response VG without value bytes."""
    return f"{cmd:02x}{mi:02x}{mx:02x}{ox:04x}{os_val:02x}{vs:04x}"


def vg_with_value(
    cmd: int, mi: int, mx: int, ox: int, os_val: int, vs: int, value: int
) -> str:
    """Build a minimal response VG with value bytes."""
    return f"{vg(cmd, mi, mx, ox, os_val, vs)}{value:0{vs * 2}x}"


CONFIRMED_HK1_RESPONSE = "020200253302000102"
CONFIRMED_HK2_RESPONSE = "020201253302000102"
CONFIRMED_HK3_RESPONSE = "020202253302000102"
CONFIRMED_SYSTEM_RESPONSE = "020100261e00000102"
CONFIRMED_ABGAS_RESPONSE = "02070025330200020197"
CONFIRMED_ANLAGENDRUCK_RESPONSE = "02090126140200020095"
CONFIRMED_KESSEL_RESPONSE = "02070025320000020192"
CONFIRMED_VOLUMENSTROM_ZERO_RESPONSE = "02090126130200020000"
CONFIRMED_RUECKLAUF_RESPONSE = "0207002537000002019d"
CONFIRMED_VORLAUFSOLL_RESPONSE = "02070025450000020050"


CONFIRMED_PARAMS = [
    {
        "key": "sg_betriebsart_hk1_vorgabe",
        "mi": 0x02,
        "mx": 0x00,
        "ox": 0x2533,
        "os": 0x02,
        "vs": 1,
    },
    {
        "key": "hk_betriebsart_vorgabe",
        "mi": 0x02,
        "mx": 0x01,
        "ox": 0x2533,
        "os": 0x02,
        "vs": 1,
    },
    {
        "key": "hk3_betriebsart_vorgabe",
        "mi": 0x02,
        "mx": 0x02,
        "ox": 0x2533,
        "os": 0x02,
        "vs": 1,
    },
    {
        "key": "sg_systembetriebsart",
        "mi": 0x01,
        "mx": 0x00,
        "ox": 0x261E,
        "os": 0x00,
        "vs": 1,
    },
    {
        "key": "wtc_abgastemperatur",
        "mi": 0x07,
        "mx": 0x00,
        "ox": 0x2533,
        "os": 0x02,
        "vs": 2,
    },
    {
        "key": "wtc_anlagendruck",
        "mi": 0x09,
        "mx": 0x01,
        "ox": 0x2614,
        "os": 0x02,
        "vs": 2,
    },
    {
        "key": "wtc_kesseltemperatur",
        "mi": 0x07,
        "mx": 0x00,
        "ox": 0x2532,
        "os": 0x00,
        "vs": 2,
    },
    {
        "key": "wtc_volumenstrom_vpt",
        "mi": 0x09,
        "mx": 0x01,
        "ox": 0x2613,
        "os": 0x02,
        "vs": 2,
    },
    {
        "key": "wtc_ruecklauftemperatur",
        "mi": 0x07,
        "mx": 0x00,
        "ox": 0x2537,
        "os": 0x00,
        "vs": 2,
    },
    {
        "key": "wtc_vorlaufsolltemperatur",
        "mi": 0x07,
        "mx": 0x00,
        "ox": 0x2545,
        "os": 0x00,
        "vs": 2,
    },
]


CONFIRMED_RESPONSES = [
    CONFIRMED_HK1_RESPONSE,
    CONFIRMED_HK2_RESPONSE,
    CONFIRMED_HK3_RESPONSE,
    CONFIRMED_SYSTEM_RESPONSE,
    CONFIRMED_ABGAS_RESPONSE,
    CONFIRMED_ANLAGENDRUCK_RESPONSE,
    CONFIRMED_KESSEL_RESPONSE,
    CONFIRMED_VOLUMENSTROM_ZERO_RESPONSE,
    CONFIRMED_RUECKLAUF_RESPONSE,
    CONFIRMED_VORLAUFSOLL_RESPONSE,
]
CONFIRMED_CORE_PARAMS = CONFIRMED_PARAMS[:5]
CONFIRMED_CORE_RESPONSES = CONFIRMED_RESPONSES[:5]


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

    async def test_read_parameters_decodes_confirmed_real_frames(self) -> None:
        """Confirmed device responses should populate all expected data keys."""
        client = ResponseClient(capi_batch_response(CONFIRMED_CORE_RESPONSES))

        result = await client.read_parameters(CONFIRMED_CORE_PARAMS)

        self.assertEqual(
            result["sg_betriebsart_hk1_vorgabe"]["value_int"],
            2,
        )
        self.assertEqual(result["hk_betriebsart_vorgabe"]["value_int"], 2)
        self.assertEqual(result["hk3_betriebsart_vorgabe"]["value_int"], 2)
        self.assertEqual(result["sg_systembetriebsart"]["value_int"], 2)
        self.assertEqual(result["wtc_abgastemperatur"]["value_int"], 407)
        self.assertEqual(result["wtc_abgastemperatur"]["value_hex"], "0197")

        request_capi = client.payloads[0]["CAPI"]
        self.assertEqual(request_capi["NN"], 5)
        self.assertEqual(
            [key for key in request_capi if key.startswith("N")],
            ["NN", "N01", "N02", "N03", "N04", "N05"],
        )
        self.assertEqual(request_capi["N01"]["VG"], "010200253302000100")
        self.assertEqual(request_capi["N02"]["VG"], "010201253302000100")
        self.assertEqual(request_capi["N03"]["VG"], "010202253302000100")
        self.assertEqual(request_capi["N04"]["VG"], "010100261e00000100")
        self.assertEqual(request_capi["N05"]["VG"], "01070025330200020000")

    async def test_read_parameters_maps_reordered_confirmed_batch_by_address(
        self,
    ) -> None:
        """Response slot order should not change the key receiving each value."""
        client = ResponseClient(
            capi_batch_response(
                [
                    CONFIRMED_ABGAS_RESPONSE,
                    CONFIRMED_SYSTEM_RESPONSE,
                    CONFIRMED_HK3_RESPONSE,
                    CONFIRMED_HK2_RESPONSE,
                    CONFIRMED_HK1_RESPONSE,
                ]
            )
        )

        result = await client.read_parameters(CONFIRMED_CORE_PARAMS)

        self.assertEqual(result["sg_betriebsart_hk1_vorgabe"]["value_int"], 2)
        self.assertEqual(result["hk_betriebsart_vorgabe"]["value_int"], 2)
        self.assertEqual(result["hk3_betriebsart_vorgabe"]["value_int"], 2)
        self.assertEqual(result["sg_systembetriebsart"]["value_int"], 2)
        self.assertEqual(result["wtc_abgastemperatur"]["value_int"], 407)

    async def test_read_parameters_keeps_missing_batch_response_isolated(
        self,
    ) -> None:
        """A missing single response should not discard the remaining batch."""
        client = ResponseClient(
            capi_batch_response(
                [
                    CONFIRMED_HK1_RESPONSE,
                    CONFIRMED_HK2_RESPONSE,
                    None,
                    CONFIRMED_SYSTEM_RESPONSE,
                    CONFIRMED_ABGAS_RESPONSE,
                ]
            )
        )

        result = await client.read_parameters(CONFIRMED_CORE_PARAMS)

        self.assertIn("sg_betriebsart_hk1_vorgabe", result)
        self.assertIn("hk_betriebsart_vorgabe", result)
        self.assertNotIn("hk3_betriebsart_vorgabe", result)
        self.assertIn("sg_systembetriebsart", result)
        self.assertEqual(result["wtc_abgastemperatur"]["value_int"], 407)

    async def test_read_parameters_decodes_mixed_confirmed_batches(self) -> None:
        """Mixed confirmed real responses should survive MAX_PARAMS splitting."""
        client = SequenceResponseClient(
            [
                capi_batch_response(CONFIRMED_RESPONSES[:6]),
                capi_batch_response(CONFIRMED_RESPONSES[6:]),
            ]
        )

        result = await client.read_parameters(CONFIRMED_PARAMS)

        self.assertEqual(result["sg_betriebsart_hk1_vorgabe"]["value_int"], 2)
        self.assertEqual(result["hk_betriebsart_vorgabe"]["value_int"], 2)
        self.assertEqual(result["hk3_betriebsart_vorgabe"]["value_int"], 2)
        self.assertEqual(result["sg_systembetriebsart"]["value_int"], 2)
        self.assertEqual(result["wtc_abgastemperatur"]["value_int"], 407)
        self.assertEqual(result["wtc_anlagendruck"]["value_int"], 149)
        self.assertEqual(result["wtc_kesseltemperatur"]["value_int"], 402)
        self.assertEqual(result["wtc_volumenstrom_vpt"]["value_int"], 0)
        self.assertEqual(result["wtc_ruecklauftemperatur"]["value_int"], 413)
        self.assertEqual(result["wtc_vorlaufsolltemperatur"]["value_int"], 80)
        self.assertEqual(client.payloads[0]["CAPI"]["NN"], 6)
        self.assertEqual(client.payloads[1]["CAPI"]["NN"], 4)
        self.assertEqual(
            [key for key in client.payloads[0]["CAPI"] if key.startswith("N")],
            ["NN", "N01", "N02", "N03", "N04", "N05", "N06"],
        )
        self.assertEqual(
            [key for key in client.payloads[1]["CAPI"] if key.startswith("N")],
            ["NN", "N01", "N02", "N03", "N04"],
        )

    async def test_read_parameters_splits_batches_with_dense_numbering(self) -> None:
        """Requests should split at 6 frames and number each batch densely."""
        params = [
            {
                "key": f"key_{index}",
                "mi": 0x01,
                "mx": 0x00,
                "ox": 0x2600 + index,
                "os": 0x00,
                "vs": 1,
            }
            for index in range(7)
        ]
        first_response = capi_batch_response(
            [
                vg_with_value(
                    api.CMD_RESPONSE,
                    param["mi"],
                    param["mx"],
                    param["ox"],
                    param["os"],
                    param["vs"],
                    2,
                )
                for param in params[:6]
            ]
        )
        second_response = capi_batch_response(
            [
                vg_with_value(
                    api.CMD_RESPONSE,
                    params[6]["mi"],
                    params[6]["mx"],
                    params[6]["ox"],
                    params[6]["os"],
                    params[6]["vs"],
                    2,
                )
            ]
        )
        client = SequenceResponseClient([first_response, second_response])

        result = await client.read_parameters(params)

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

    async def test_probe_parameter_classifies_error_as_absent(self) -> None:
        """CMD_ERROR should be a confirmed negative presence probe."""
        client = ResponseClient(
            capi_response(vg(api.CMD_ERROR, 0x04, 0x00, 0x2501, 0x00, 2))
        )

        status, data = await client.probe_parameter(0x04, 0x00, 0x2501, 0x00, 2)

        self.assertEqual(status, api.ProbeStatus.ABSENT)
        self.assertIsNotNone(data)

    async def test_probe_parameter_classifies_empty_response_as_unknown(self) -> None:
        """Empty responses should not be treated as confirmed absence."""
        client = ResponseClient(None)

        status, data = await client.probe_parameter(0x04, 0x00, 0x2501, 0x00, 2)

        self.assertEqual(status, api.ProbeStatus.UNKNOWN)
        self.assertIsNone(data)

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

    async def test_write_parameter_rejects_value_mismatch_when_ack_contains_value(
        self,
    ) -> None:
        """ACK value payload should match the requested raw value when present."""
        client = ResponseClient(
            capi_response(vg_with_value(api.CMD_ACK, 0x03, 0x00, 0x2539, 0x02, 2, 501))
        )

        self.assertFalse(
            await client.write_parameter(0x03, 0x00, 0x2539, 0x02, 2, 500)
        )


if __name__ == "__main__":
    unittest.main()
