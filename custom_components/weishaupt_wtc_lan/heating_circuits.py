"""Helpers for building dynamic heating circuit sensor definitions."""

from __future__ import annotations

from dataclasses import replace

from .sensors import (
    HK_SENSORS,
    SG_SENSORS,
    SOL_SENSORS,
    WTC_SENSORS,
    WeishauptSensorDefinition,
)

HK3_MODBUS_OFFSET = 30

DEVICE_GROUP_SYSTEM = "system"
DEVICE_GROUP_WTC = "wtc"
DEVICE_GROUP_WW = "ww"
DEVICE_GROUP_SOL = "sol"

SYSTABLE_DEVICE_GROUP_MARKERS = {
    DEVICE_GROUP_WTC: (
        "wtc",
        "kessel",
        "brennwert",
        "boiler",
    ),
    DEVICE_GROUP_WW: (
        "em-ww",
        "warmwasser",
        "domestic hot water",
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

PRESENCE_SENTINELS = {
    2: {0x8000, 0xFFFF},
    4: {0x80000000, 0xFFFFFFFF},
}


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
    heating_suffix = heating_circuit_device_suffix(sensor_def)
    if heating_suffix:
        return heating_suffix
    if sensor_def.key in WARM_WATER_SENSOR_KEYS:
        return "ww"
    return sensor_def.group.value


def logical_group_for_sensor(sensor_def: WeishauptSensorDefinition) -> str:
    """Return the logical group used for dynamic device filtering."""
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
