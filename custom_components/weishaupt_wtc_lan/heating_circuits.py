"""Helpers for building dynamic heating circuit sensor definitions."""

from __future__ import annotations

import csv
from dataclasses import replace
import logging
import re

from .const import NETWORK_DEVICE_SUFFIX
from .sensors import (
    HK_SENSORS,
    NETWORK_SENSORS,
    SG_SENSORS,
    SOL_SENSORS,
    WTC_SENSORS,
    WeishauptSensorDefinition,
)

_LOGGER = logging.getLogger(__name__)

HK3_MODBUS_OFFSET = 30

DEVICE_GROUP_SYSTEM = "system"
DEVICE_GROUP_WTC = "wtc"
DEVICE_GROUP_WW = "ww"
DEVICE_GROUP_SOL = "sol"

SYSTABLE_LOGICAL_DEVICE_MODULES = {
    "m01": DEVICE_GROUP_SYSTEM,
    "m03": DEVICE_GROUP_WW,
    "m06": NETWORK_DEVICE_SUFFIX,
    "m07": DEVICE_GROUP_WTC,
}

SYSTABLE_DEVICE_GROUP_MARKERS = {
    DEVICE_GROUP_WTC: (
        "wtc",
        "kessel",
        "brennwert",
        "boiler",
        "m07_",
    ),
    DEVICE_GROUP_WW: (
        "em-ww",
        "warmwasser",
        "domestic hot water",
        "m03_",
    ),
    DEVICE_GROUP_SOL: (
        "em-sol",
        "solar",
        "solarmodul",
    ),
}

HK1_SENSOR_KEYS = {
    "sg_betriebsart_hk1_vorgabe",
    "sg_sowi_umschaltung_hk1",
    "sg_betriebsart_hk1_aktuell",
    "sg_status_hk1",
    "sg_raumsolltemperatur_komfort",
    "sg_raumsolltemperatur_normal",
    "sg_raumsolltemperatur_absenk",
    "sg_raumsolltemperatur_aktuell",
    "sg_vorlaufsolltemperatur_komfort",
    "sg_vorlaufsolltemperatur_normal",
    "sg_vorlaufsolltemperatur_absenk",
    "sg_vorlaufsolltemperatur_sonderniveau",
    "sg_vorlaufsolltemperatur_aktuell",
    "sg_vorlaufisttemperatur",
}

WARM_WATER_SENSOR_KEYS = {
    "sg_status_warmwasser",
    "sg_warmwasser_push",
    "sg_wwsolltemperatur_normal",
    "sg_wwsolltemperatur_absenk",
    "sg_wwsolltemperatur_aktuell",
    "sg_warmwassertemperatur",
    "sg_ruecklauftemperatur_zirkulation",
    "sg_pumpe_warmwasser",
}

NUMBER_SENSOR_KEYS = {
    "sg_wwsolltemperatur_normal",
    "sg_wwsolltemperatur_absenk",
}

SELECT_SENSOR_KEYS = {
    "sg_betriebsart_hk1_vorgabe",
    "sg_systembetriebsart",
}

WRITABLE_OPERATING_MODE_SENSOR_KEYS = {
    "sg_betriebsart_hk1_vorgabe",
    "hk_betriebsart_vorgabe",
    "hk3_betriebsart_vorgabe",
    "sg_systembetriebsart",
}

NETWORK_SENSOR_KEYS = {sensor_def.key for sensor_def in NETWORK_SENSORS}

PRESENCE_SENTINELS = {
    2: {0x8000, 0xFFFF},
    4: {0x80000000, 0xFFFFFFFF},
}

_HK_MARKER_RE = re.compile(r"\b(?:hk|heizkreis)\s*([123])\b", re.IGNORECASE)
_HK_NAME_MARKER_RE = re.compile(r"\b(?:hk|heizkreis)\s*[123]\b", re.IGNORECASE)
_SYSTABLE_NAME_NOISE = {
    "address",
    "adresse",
    "device",
    "geraet",
    "gerät",
    "group",
    "id",
    "index",
    "mi",
    "module",
    "mx",
    "name",
    "os",
    "ox",
    "parameter",
    "register",
    "type",
    "typ",
    "value",
    "wert",
    "vs",
}

_SYSTABLE_NAME_HEADERS = {
    "bezeichnung",
    "display",
    "displayname",
    "label",
    "name",
    "text",
    "title",
}

_SYSTABLE_MI_HEADERS = {"mi", "moduleindex", "module_index", "module"}
_SYSTABLE_MX_HEADERS = {"mx", "memberindex", "member_index", "member"}
_SYSTABLE_MODULE_RE = re.compile(r"^(m\d{2})_.*\.bin$", re.IGNORECASE)


def heating_circuit_for_sensor(sensor_def: WeishauptSensorDefinition) -> int | None:
    """Return the logical heating circuit for a sensor definition."""
    if sensor_def.key in HK1_SENSOR_KEYS:
        return 1
    if sensor_def.key.startswith("hk3_"):
        return 3
    if sensor_def.key.startswith("hk_"):
        return 2
    return None


def heating_circuit_device_suffix(sensor_def: WeishauptSensorDefinition) -> str | None:
    """Return the device identifier suffix for external heating circuits."""
    circuit = heating_circuit_for_sensor(sensor_def)
    if circuit == 1:
        return "hk1"
    if circuit == 2:
        return "hk"
    if circuit == 3:
        return "hk3"
    return None


def device_suffix_for_sensor(sensor_def: WeishauptSensorDefinition) -> str:
    """Return the logical device suffix for a sensor definition."""
    if sensor_def.key in NETWORK_SENSOR_KEYS:
        return NETWORK_DEVICE_SUFFIX
    heating_suffix = heating_circuit_device_suffix(sensor_def)
    if heating_suffix:
        return heating_suffix
    if sensor_def.key in WARM_WATER_SENSOR_KEYS:
        return "ww"
    return sensor_def.group.value


def is_writable_operating_mode_definition(
    sensor_def: WeishauptSensorDefinition,
) -> bool:
    """Return True for writable operating-mode target definitions."""
    return (
        sensor_def.key in WRITABLE_OPERATING_MODE_SENSOR_KEYS
        or (
            sensor_def.mi == 0x02
            and sensor_def.ox == 0x2533
            and sensor_def.os == 0x02
            and sensor_def.vs == 1
            and sensor_def.value_map is not None
        )
    )


def logical_group_for_sensor(sensor_def: WeishauptSensorDefinition) -> str:
    """Return the logical group used for dynamic device filtering."""
    if sensor_def.key in NETWORK_SENSOR_KEYS:
        return DEVICE_GROUP_SYSTEM
    if sensor_def.key in WARM_WATER_SENSOR_KEYS:
        return DEVICE_GROUP_WW
    if sensor_def.group.value == DEVICE_GROUP_SOL:
        return DEVICE_GROUP_SOL
    if sensor_def.group.value == DEVICE_GROUP_WTC:
        return DEVICE_GROUP_WTC
    return DEVICE_GROUP_SYSTEM


def probe_sensor_definitions_for_group(
    group: str, limit: int = 5
) -> list[WeishauptSensorDefinition]:
    """Return characteristic definitions for setup-time presence probing."""
    definitions: list[WeishauptSensorDefinition]
    if group == DEVICE_GROUP_WTC:
        definitions = WTC_SENSORS
    elif group == DEVICE_GROUP_SOL:
        definitions = SOL_SENSORS
    elif group == DEVICE_GROUP_WW:
        definitions = [
            sensor_def
            for sensor_def in SG_SENSORS
            if sensor_def.key in WARM_WATER_SENSOR_KEYS
            and sensor_def.key != "sg_warmwasser_push"
        ]
    else:
        definitions = []

    return [sensor_def for sensor_def in definitions if sensor_def.poll][:limit]


def is_plausible_presence_value(sensor_def: WeishauptSensorDefinition, data: dict) -> bool:
    """Return True if a read response can prove that a module exists."""
    raw_value = data.get("value_int")
    if raw_value is None:
        return False
    value_size = sensor_def.byte_length or sensor_def.vs
    if raw_value in PRESENCE_SENTINELS.get(value_size, set()):
        return False
    return True


def device_groups_from_systable_csv(csv_text: str) -> set[str]:
    """Extract logical device groups from the read-only systable.csv metadata."""
    text = csv_text.casefold()
    groups: set[str] = set()
    for group, markers in SYSTABLE_DEVICE_GROUP_MARKERS.items():
        if any(marker in text for marker in markers):
            groups.add(group)
    return groups


def _systable_rows(csv_text: str) -> list[list[str]]:
    """Return loose CSV rows from systable text using common delimiters."""
    rows: list[list[str]] = []
    for raw_line in csv_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        delimiter = ";"
        for candidate in (";", "\t", ","):
            if candidate in line:
                delimiter = candidate
                break
        try:
            rows.extend(csv.reader([line], delimiter=delimiter))
        except csv.Error:
            rows.append(re.split(r"[;,\t]", line))
    return rows


def _normalized_header(value: str) -> str:
    """Normalize a CSV header name for conservative field matching."""
    value = value.strip().strip('"').strip("'").casefold()
    return re.sub(r"[^a-z0-9_]", "", value)


def _looks_like_header(row: list[str]) -> bool:
    """Return True when a row looks like CSV headers."""
    normalized = {_normalized_header(value) for value in row}
    return bool(
        normalized
        & (
            _SYSTABLE_NAME_HEADERS
            | _SYSTABLE_MI_HEADERS
            | _SYSTABLE_MX_HEADERS
        )
    )


def _parse_systable_int(value: str) -> int | None:
    """Parse decimal or hex-ish metadata integers."""
    match = re.search(r"(?:0x)?[0-9a-fA-F]+", value or "")
    if match is None:
        return None
    raw = match.group(0)
    base = 16 if raw.lower().startswith("0x") else 10
    try:
        return int(raw, base)
    except ValueError:
        return None


def _heating_circuit_from_address_fields(fields: dict[str, str]) -> int | None:
    """Return HK circuit from confirmed MI/MX metadata fields."""
    mi_value: int | None = None
    mx_value: int | None = None
    for key, value in fields.items():
        normalized = _normalized_header(key)
        if normalized in _SYSTABLE_MI_HEADERS:
            mi_value = _parse_systable_int(value)
        elif normalized in _SYSTABLE_MX_HEADERS:
            mx_value = _parse_systable_int(value)

    if mi_value == 0x02 and mx_value in (0x00, 0x01, 0x02):
        return int(mx_value) + 1
    return None


def _heating_circuit_from_inline_address(raw_line: str) -> int | None:
    """Return HK circuit from inline MI/MX text when real metadata uses labels."""
    mi_match = re.search(r"\bMI\s*=?\s*(0x[0-9a-fA-F]+|\d+)", raw_line, re.IGNORECASE)
    mx_match = re.search(r"\bMX\s*=?\s*(0x[0-9a-fA-F]+|\d+)", raw_line, re.IGNORECASE)
    if not mi_match or not mx_match:
        return None
    mi_value = _parse_systable_int(mi_match.group(1))
    mx_value = _parse_systable_int(mx_match.group(1))
    if mi_value == 0x02 and mx_value in (0x00, 0x01, 0x02):
        return int(mx_value) + 1
    return None


def _real_systable_module(row: list[str]) -> str | None:
    """Return the real systable module token such as m02 from M02_*.BIN."""
    for field in row:
        match = _SYSTABLE_MODULE_RE.match(field.strip())
        if match is not None:
            return match.group(1).casefold()
    return None


def _real_systable_name(row: list[str]) -> str | None:
    """Return the display name following the Mxx_*.BIN field in real systable rows."""
    for index, field in enumerate(row):
        if _SYSTABLE_MODULE_RE.match(field.strip()) and index + 1 < len(row):
            candidate = _clean_systable_name(row[index + 1])
            if _is_systable_name_candidate(candidate):
                return candidate
    return None


def _real_systable_circuit(row: list[str]) -> int | None:
    """Return the final-column HK circuit number for real M02 module rows."""
    if _real_systable_module(row) != "m02" or not row:
        return None
    try:
        circuit = int(row[-1].strip())
    except (TypeError, ValueError):
        return None
    return circuit if circuit in (1, 2, 3) else None


def logical_device_names_from_systable_csv(csv_text: str | None) -> dict[str, str]:
    """Extract optional logical device display names from real systable rows."""
    if not csv_text:
        return {}
    names: dict[str, str] = {}
    for row in _systable_rows(csv_text):
        raw_fields = [field.strip() for field in row if field.strip()]
        module = _real_systable_module(raw_fields)
        group = SYSTABLE_LOGICAL_DEVICE_MODULES.get(module or "")
        if group is None or group in names:
            continue
        name = _real_systable_name(raw_fields)
        if name:
            names[group] = name
    _LOGGER.debug("Parsed logical device names from systable.csv: %s", names)
    return names


def _clean_systable_name(value: str) -> str:
    """Normalize a possible display name from a systable field."""
    value = value.strip().strip('"').strip("'").strip()
    value = _HK_NAME_MARKER_RE.sub("", value)
    value = value.replace("->", " ").replace(":", " ").replace("=", " ")
    value = re.sub(r"\s+", " ", value).strip(" -_/")
    return value


def _is_systable_name_candidate(value: str) -> bool:
    """Return True when a field looks like a user-facing heating-circuit name."""
    if not value or not any(char.isalpha() for char in value):
        return False
    folded = value.casefold()
    if folded in _SYSTABLE_NAME_NOISE:
        return False
    if folded.startswith(("0x", "wem", "em-hk")):
        return False
    if all(part.casefold() in _SYSTABLE_NAME_NOISE for part in folded.split()):
        return False
    return True


def heating_circuit_names_from_systable_csv(csv_text: str | None) -> dict[int, str]:
    """Extract heating-circuit display names from systable.csv when present."""
    if not csv_text:
        _LOGGER.debug("No systable.csv content available for heating-circuit names")
        return {}

    rows = _systable_rows(csv_text)
    _LOGGER.debug(
        "Parsing systable.csv for heating-circuit names: chars=%s rows=%s",
        len(csv_text),
        len(rows),
    )
    header: list[str] | None = None
    names: dict[int, str] = {}
    for row in rows:
        raw_fields = [field.strip() for field in row if field.strip()]
        if not raw_fields:
            continue
        if header is None and _looks_like_header(raw_fields):
            header = raw_fields
            continue

        fields_by_header = (
            dict(zip(header, raw_fields, strict=False)) if header is not None else {}
        )
        real_circuit = _real_systable_circuit(raw_fields)
        if real_circuit is not None and real_circuit not in names:
            real_name = _real_systable_name(raw_fields)
            if real_name:
                names[real_circuit] = real_name
                continue

        raw_line = " ".join(raw_fields)
        marker = _HK_MARKER_RE.search(raw_line)
        if marker is not None:
            circuit = int(marker.group(1))
        else:
            circuit = _heating_circuit_from_address_fields(fields_by_header)
            if circuit is None:
                circuit = _heating_circuit_from_inline_address(raw_line)
        if circuit is None:
            continue
        if circuit in names:
            continue

        candidates: list[str] = []
        for key, value in fields_by_header.items():
            if _normalized_header(key) in _SYSTABLE_NAME_HEADERS:
                candidates.append(_clean_systable_name(value))
        candidates.extend(_clean_systable_name(field) for field in raw_fields)
        candidates.extend(
            _clean_systable_name(part)
            for part in re.split(r"->|:|=", raw_line)
        )
        for candidate in candidates:
            if _is_systable_name_candidate(candidate):
                names[circuit] = candidate
                break
    _LOGGER.debug("Parsed heating-circuit names from systable.csv: %s", names)
    return names


def serialize_heating_circuit_names(names: dict[int, str] | None) -> dict[str, str]:
    """Serialize heating-circuit names for config-entry storage."""
    if not names:
        return {}
    return {
        str(circuit): name.strip()
        for circuit, name in names.items()
        if circuit in (1, 2, 3) and name and name.strip()
    }


def heating_circuit_names_from_config(value: object) -> dict[int, str]:
    """Normalize persisted heating-circuit names from config-entry data."""
    if not isinstance(value, dict):
        return {}
    names: dict[int, str] = {}
    for raw_circuit, raw_name in value.items():
        try:
            circuit = int(raw_circuit)
        except (TypeError, ValueError):
            continue
        if circuit not in (1, 2, 3) or raw_name is None:
            continue
        name = str(raw_name).strip()
        if name:
            names[circuit] = name
    return names


def resolve_heating_circuit_names(
    overrides: dict[int, str | None] | None,
    detected_names: dict[int, str] | None,
    use_detected_names: bool,
    fallbacks: dict[int, str],
) -> dict[int, str]:
    """Resolve display names from explicit overrides, detected names, and defaults."""
    overrides = overrides or {}
    detected_names = detected_names or {}
    resolved: dict[int, str] = {}
    for circuit in (1, 2, 3):
        explicit = (overrides.get(circuit) or "").strip()
        if explicit:
            resolved[circuit] = explicit
            continue
        detected = (detected_names.get(circuit) or "").strip()
        if use_detected_names and detected:
            resolved[circuit] = detected
            continue
        resolved[circuit] = fallbacks[circuit]
    _LOGGER.debug(
        "Resolved heating-circuit names: overrides=%s detected=%s use_detected=%s resolved=%s",
        overrides,
        detected_names,
        use_detected_names,
        resolved,
    )
    return resolved


def _offset_modbus_register(register: str, offset: int) -> str:
    if not register:
        return register
    return str(int(register) + offset)


def build_hk_sensor_definitions(
    circuit_number: int, mx: int
) -> list[WeishauptSensorDefinition]:
    """Build sensor definitions for an external heating circuit."""
    if circuit_number == 2:
        return list(HK_SENSORS)

    if circuit_number != 3:
        raise ValueError(f"Unsupported external heating circuit HK{circuit_number}")

    return [
        replace(
            sensor_def,
            key=sensor_def.key.replace("hk_", "hk3_", 1),
            name=sensor_def.name.replace("HK ", "HK3 ", 1),
            mx=mx,
            modbus_reg=_offset_modbus_register(sensor_def.modbus_reg, HK3_MODBUS_OFFSET),
        )
        for sensor_def in HK_SENSORS
    ]


def build_sensor_definitions(
    active_heating_circuits: list[int],
    active_device_groups: set[str] | None = None,
) -> list[WeishauptSensorDefinition]:
    """Build all sensor definitions for detected heating circuits."""
    active_device_groups = active_device_groups or {
        DEVICE_GROUP_SYSTEM,
        DEVICE_GROUP_WTC,
        DEVICE_GROUP_WW,
        DEVICE_GROUP_SOL,
    }
    sensor_definitions = [
        sensor_def
        for sensor_def in SG_SENSORS
        if logical_group_for_sensor(sensor_def) in active_device_groups
    ]

    if DEVICE_GROUP_WTC in active_device_groups:
        sensor_definitions.extend(WTC_SENSORS)
    if DEVICE_GROUP_SOL in active_device_groups:
        sensor_definitions.extend(SOL_SENSORS)

    if 2 in active_heating_circuits:
        sensor_definitions.extend(build_hk_sensor_definitions(2, 0x01))
    if 3 in active_heating_circuits:
        sensor_definitions.extend(build_hk_sensor_definitions(3, 0x02))

    return sensor_definitions


def build_polled_sensor_definitions(
    sensor_definitions: list[WeishauptSensorDefinition],
) -> list[WeishauptSensorDefinition]:
    """Return only definitions that should be polled."""
    return [sensor_def for sensor_def in sensor_definitions if sensor_def.poll]
