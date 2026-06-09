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


def heating_circuit_for_sensor(sensor_def: WeishauptSensorDefinition) -> int | None:
    """Return the logical heating circuit for a sensor definition."""
    if sensor_def.key == "sg_betriebsart_hk1_vorgabe":
        return 1
    if sensor_def.key.startswith("hk3_"):
        return 3
    if sensor_def.key.startswith("hk_"):
        return 2
    return None


def heating_circuit_device_suffix(sensor_def: WeishauptSensorDefinition) -> str | None:
    """Return the device identifier suffix for external heating circuits."""
    circuit = heating_circuit_for_sensor(sensor_def)
    if circuit == 2:
        return "hk"
    if circuit == 3:
        return "hk3"
    return None


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
) -> list[WeishauptSensorDefinition]:
    """Build all sensor definitions for detected heating circuits."""
    sensor_definitions = list(SG_SENSORS) + list(WTC_SENSORS) + list(SOL_SENSORS)

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
