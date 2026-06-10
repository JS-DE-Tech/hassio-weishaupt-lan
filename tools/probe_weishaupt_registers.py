"""Read-only probe for empirically confirmed Weishaupt CanApiJson registers.

The script sends only GET frames to /ajax/CanApiJson.json. It never sends SET
commands and never prints credentials.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import HTTPBasicAuthHandler, HTTPPasswordMgrWithDefaultRealm
from urllib.request import Request, build_opener


REQUEST_ID = "12345678"
SRC_DDC = "DDC"
MAX_PARAMS_PER_REQUEST = 6


@dataclass(frozen=True)
class Probe:
    """A read-only register probe."""

    key: str
    name: str
    mi: int
    mx: int
    ox: int
    os: int
    vs: int
    scale: float = 1.0
    signed: bool = False
    unit: str = ""
    value_map: dict[int, str] | None = None


MODE_MAP = {
    1: "Standby",
    2: "Zeitprogramm 1",
    3: "Zeitprogramm 2",
    4: "Zeitprogramm 3",
    5: "Sommer",
    6: "Komfort",
    7: "Normal",
    8: "Absenk",
}

SYSTEM_MODE_MAP = {
    1: "Standby",
    2: "Sommer",
    3: "Automatik",
}

PROBES = (
    Probe("sg_betriebsart_hk1_vorgabe", "HK1 Betriebsart Vorgabe", 0x02, 0x00, 0x2533, 0x02, 1, value_map=MODE_MAP),
    Probe("hk_betriebsart_vorgabe", "HK2 Betriebsart Vorgabe", 0x02, 0x01, 0x2533, 0x02, 1, value_map=MODE_MAP),
    Probe("hk3_betriebsart_vorgabe", "HK3 Betriebsart Vorgabe", 0x02, 0x02, 0x2533, 0x02, 1, value_map=MODE_MAP),
    Probe("sg_systembetriebsart", "Systembetriebsart", 0x01, 0x00, 0x261E, 0x00, 1, value_map=SYSTEM_MODE_MAP),
    Probe("wtc_anlagendruck", "Anlagendruck", 0x09, 0x01, 0x2614, 0x02, 2, scale=0.01, unit="bar"),
    Probe("wtc_kesseltemperatur", "Kesseltemperatur", 0x07, 0x00, 0x2532, 0x00, 2, scale=0.1, signed=True, unit="degC"),
    Probe("wtc_volumenstrom_vpt", "Volumenstrom VPT", 0x09, 0x01, 0x2613, 0x02, 2, unit="l/h"),
    Probe("wtc_abgastemperatur", "WTC Abgastemperatur", 0x07, 0x00, 0x2533, 0x02, 2, scale=0.1, signed=True, unit="degC"),
    Probe("wtc_ruecklauftemperatur", "WTC Ruecklauftemperatur", 0x07, 0x00, 0x2537, 0x00, 2, scale=0.1, signed=True, unit="degC"),
    Probe("wtc_vorlaufsolltemperatur", "WTC Vorlaufsolltemperatur", 0x07, 0x00, 0x2545, 0x00, 2, scale=0.1, signed=True, unit="degC"),
)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(
        description="Read confirmed Weishaupt registers without writing values."
    )
    parser.add_argument("--host", required=True, help="Weishaupt SG host or IP")
    parser.add_argument(
        "--username",
        default=os.environ.get("WEISHAUPT_USERNAME", "admin"),
        help="HTTP username; defaults to WEISHAUPT_USERNAME or admin",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("WEISHAUPT_PASSWORD"),
        help="HTTP password; defaults to WEISHAUPT_PASSWORD",
    )
    return parser


def build_opener_for(base_url: str, username: str, password: str | None):
    """Create an opener with optional Basic Auth."""
    if not password:
        return build_opener()

    password_mgr = HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, base_url, username, password)
    return build_opener(HTTPBasicAuthHandler(password_mgr))


def build_read_vg(probe: Probe) -> str:
    """Build a read-only CanApiJson VG frame."""
    padding = "00" * probe.vs
    return (
        f"01{probe.mi:02x}{probe.mx:02x}{probe.ox:04x}"
        f"{probe.os:02x}{probe.vs:04x}{padding}"
    )


def parse_vg(vg: str) -> dict:
    """Parse the relevant parts of a CanApiJson VG response."""
    if len(vg) < 16:
        raise ValueError(f"VG frame too short: {vg}")
    value_hex = vg[16:]
    return {
        "cmd": int(vg[0:2], 16),
        "mi": int(vg[2:4], 16),
        "mx": int(vg[4:6], 16),
        "ox": int(vg[6:10], 16),
        "os": int(vg[10:12], 16),
        "vs": int(vg[12:16], 16),
        "value_hex": value_hex,
        "value_int": int(value_hex, 16) if value_hex else 0,
    }


def decode_value(probe: Probe, raw_value: int) -> str:
    """Decode a raw value for display."""
    if probe.value_map:
        return probe.value_map.get(raw_value, f"Unknown ({raw_value})")

    value = raw_value
    if probe.signed and probe.vs == 2 and value > 0x7FFF:
        value -= 0x10000
    elif probe.signed and probe.vs == 4 and value > 0x7FFFFFFF:
        value -= 0x100000000
    value = round(value * probe.scale, 2)
    return f"{value:g} {probe.unit}".strip()


def post_batch(opener, url: str, probes: tuple[Probe, ...]) -> dict:
    """Send one read-only CanApiJson batch."""
    capi = {"NN": len(probes)}
    for index, probe in enumerate(probes, start=1):
        capi[f"N{index:02d}"] = {"VG": build_read_vg(probe)}

    body = json.dumps({"ID": REQUEST_ID, "SRC": SRC_DDC, "CAPI": capi}).encode()
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    """Run the read-only register probe."""
    args = build_arg_parser().parse_args()
    host = args.host.removeprefix("http://").removeprefix("https://").strip("/")
    base_url = f"http://{host}"
    opener = build_opener_for(base_url, args.username, args.password)
    url = f"{base_url}/ajax/CanApiJson.json"

    for start in range(0, len(PROBES), MAX_PARAMS_PER_REQUEST):
        batch = PROBES[start : start + MAX_PARAMS_PER_REQUEST]
        try:
            response = post_batch(opener, url, batch)
        except (HTTPError, URLError, TimeoutError) as err:
            print(f"Batch {start // MAX_PARAMS_PER_REQUEST + 1}: failed ({err})")
            continue

        capi = response.get("CAPI", {})
        for index, probe in enumerate(batch, start=1):
            response_vg = capi.get(f"N{index:02d}", {}).get("VG")
            if not response_vg:
                print(f"{probe.key}: missing response")
                continue
            parsed = parse_vg(response_vg)
            raw_value = parsed["value_int"]
            print(
                f"{probe.key}: request={build_read_vg(probe)} "
                f"response={response_vg} raw=0x{raw_value:0{probe.vs * 2}x} "
                f"int={raw_value} decoded={decode_value(probe, raw_value)}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
