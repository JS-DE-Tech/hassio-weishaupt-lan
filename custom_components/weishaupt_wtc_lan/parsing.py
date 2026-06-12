"""Pure parsing helpers for Weishaupt sensor values."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Any


def extract_value_segment(
    value_hex: str,
    byte_offset: int,
    byte_length: int,
) -> tuple[str, int] | None:
    """Extract a byte segment from a raw VG value hex string."""
    start = byte_offset * 2
    end = start + (byte_length * 2)
    if len(value_hex) < end:
        return None

    segment = value_hex[start:end]
    return segment, int(segment, 16)


def decode_fault_status(raw_value: int) -> str:
    """Decode the fault status bitfield from register 121."""
    message_type = raw_value & 0x0F
    if message_type == 1:
        return "Fehler"
    if message_type == 2:
        return "Warnung"
    if message_type == 3:
        return "Info"
    if (raw_value >> 8) > 0:
        return "Fehler aktiv"
    return "Keine Meldung"


def decode_fault_status_attributes(raw_value: int) -> dict[str, Any]:
    """Decode fault status details from register 121."""
    return {
        "error_active": (raw_value >> 8) > 0,
        "system_error": bool(raw_value & 0x10),
        "message_type": decode_fault_status(raw_value),
        "module_error": not bool(raw_value & 0x10),
    }


def decode_module_attributes(raw_value: int) -> dict[str, int]:
    """Decode module identifier fields from register 123."""
    return {
        "module_id": (raw_value >> 8) & 0xFF,
        "module_index": raw_value & 0xFF,
    }


def build_device_time_iso(values: Mapping[str, int]) -> str | None:
    """Build an ISO timestamp from separate SG time/date component values."""
    year = values.get("sg_datum_jahr", 0)
    if year < 100:
        year += 2000

    try:
        dt = datetime(
            year,
            values.get("sg_datum_monat", 1),
            values.get("sg_datum_tag", 1),
            values.get("sg_uhrzeit_stunden", 0),
            values.get("sg_uhrzeit_minuten", 0),
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None

    return dt.isoformat()


def _device_year(values: Mapping[str, int]) -> int:
    year = values.get("sg_datum_jahr", 0)
    if year < 100:
        year += 2000
    return year


def build_device_date(values: Mapping[str, int]) -> str | None:
    """Build a DD.MM.YYYY date from separate SG date component values."""
    try:
        dt = datetime(
            _device_year(values),
            values.get("sg_datum_monat", 1),
            values.get("sg_datum_tag", 1),
        )
    except ValueError:
        return None
    return dt.strftime("%d.%m.%Y")


def build_device_clock_time(values: Mapping[str, int]) -> str | None:
    """Build a HH:MM time from separate SG time component values."""
    hour = values.get("sg_uhrzeit_stunden", 0)
    minute = values.get("sg_uhrzeit_minuten", 0)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def decode_ipv4(raw_value: int, value_hex: str = "") -> str | None:
    """Decode a 4-byte integer or value hex string into dotted IPv4 notation."""
    if value_hex:
        value_hex = value_hex.zfill(8)[-8:]
        try:
            octets = [int(value_hex[index : index + 2], 16) for index in range(0, 8, 2)]
        except ValueError:
            return None
    else:
        if not 0 <= raw_value <= 0xFFFFFFFF:
            return None
        octets = [
            (raw_value >> 24) & 0xFF,
            (raw_value >> 16) & 0xFF,
            (raw_value >> 8) & 0xFF,
            raw_value & 0xFF,
        ]
    return ".".join(str(octet) for octet in octets)


def format_mac_address(components: list[int]) -> str | None:
    """Format six MAC address byte components as XX-XX-XX-XX-XX-XX."""
    if len(components) != 6:
        return None
    if any(not 0 <= component <= 0xFF for component in components):
        return None
    return "-".join(f"{component:02X}" for component in components)
