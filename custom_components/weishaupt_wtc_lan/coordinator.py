"""DataUpdateCoordinator for Weishaupt WTC."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WeishauptApiClient, WeishauptApiError, WeishauptConnectionError
from .const import DOMAIN
from .heating_circuits import build_polled_sensor_definitions
from .sensors import WeishauptSensorDefinition

_LOGGER = logging.getLogger(__name__)

DEBUG_STATE_KEYS = {
    "sg_betriebsart_hk1_vorgabe",
    "sg_betriebsart_hk1_aktuell",
    "sg_status_hk1",
    "hk_betriebsart_vorgabe",
    "hk_betriebsart_aktuell",
    "hk_status",
    "hk3_betriebsart_vorgabe",
    "hk3_betriebsart_aktuell",
    "hk3_status",
    "sg_systembetriebsart",
    "wtc_anlagendruck",
    "wtc_abgastemperatur",
    "wtc_kesseltemperatur",
    "wtc_ruecklauftemperatur",
    "wtc_volumenstrom_vpt",
    "wtc_vorlaufsolltemperatur",
}


class WeishauptDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching data from Weishaupt device."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: WeishauptApiClient,
        scan_interval: int = 30,
        sensor_definitions: list[WeishauptSensorDefinition] | None = None,
        active_heating_circuits: list[int] | None = None,
        heating_circuit_names: dict[int, str] | None = None,
        active_device_groups: set[str] | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.sensor_definitions = sensor_definitions or []
        self.polled_sensor_definitions = build_polled_sensor_definitions(
            self.sensor_definitions
        )
        self.active_heating_circuits = active_heating_circuits or [1]
        self.heating_circuit_names = heating_circuit_names or {}
        self.active_device_groups = active_device_groups or set()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Weishaupt device."""
        params = []
        for sensor_def in self.polled_sensor_definitions:
            params.append(
                {
                    "key": sensor_def.key,
                    "mi": sensor_def.mi,
                    "mx": sensor_def.mx,
                    "ox": sensor_def.ox,
                    "os": sensor_def.os,
                    "vs": sensor_def.vs,
                }
            )

        try:
            results = await self.client.read_parameters(params)
        except WeishauptConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except WeishauptApiError as err:
            raise UpdateFailed(f"API error: {err}") from err

        definitions_by_key = {
            sensor_def.key: sensor_def for sensor_def in self.polled_sensor_definitions
        }
        for key in DEBUG_STATE_KEYS:
            sensor_def = definitions_by_key.get(key)
            if sensor_def is None:
                continue
            data = results.get(key)
            if data is None:
                _LOGGER.debug(
                    "Coordinator refresh missing key=%s MI=0x%02x MX=0x%02x OX=0x%04x OS=0x%02x VS=%s",
                    key,
                    sensor_def.mi,
                    sensor_def.mx,
                    sensor_def.ox,
                    sensor_def.os,
                    sensor_def.vs,
                )
                continue
            _LOGGER.debug(
                "Coordinator refresh key=%s MI=0x%02x MX=0x%02x OX=0x%04x OS=0x%02x VS=%s response VG=%s raw_value_hex=%s raw_value_int=%s",
                key,
                sensor_def.mi,
                sensor_def.mx,
                sensor_def.ox,
                sensor_def.os,
                sensor_def.vs,
                data.get("vg", ""),
                data.get("value_hex", ""),
                data.get("value_int"),
            )

        return results
