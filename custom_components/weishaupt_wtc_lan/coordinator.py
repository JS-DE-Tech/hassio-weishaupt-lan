"""DataUpdateCoordinator for Weishaupt WTC."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WeishauptApiClient, WeishauptApiError, WeishauptConnectionError
from .const import DOMAIN
from .heating_circuits import build_polled_sensor_definitions
from .sensors import ExperimentalWtcRegister, WeishauptSensorDefinition

_LOGGER = logging.getLogger(__name__)

NETWORK_REFRESH_INTERVAL = timedelta(minutes=10)

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
        logical_device_names: dict[str, str] | None = None,
        active_device_groups: set[str] | None = None,
        experimental_wtc_registers: list[ExperimentalWtcRegister] | None = None,
        extended_experimental_wtc_registers: list[ExperimentalWtcRegister] | None = None,
        static_data: dict[str, Any] | None = None,
        network_refresh_callback: Callable[[], Awaitable[dict[str, Any]]] | None = None,
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
        self.logical_device_names = logical_device_names or {}
        self.active_device_groups = active_device_groups or set()
        self.experimental_wtc_registers = experimental_wtc_registers or []
        self.extended_experimental_wtc_registers = (
            extended_experimental_wtc_registers or []
        )
        self.static_data = static_data or {}
        self.network_refresh_callback = network_refresh_callback
        self._last_network_refresh = (
            datetime.now(timezone.utc) if network_refresh_callback is not None else None
        )

    async def async_refresh_network_diagnostics(
        self,
        *,
        force: bool = False,
        now: datetime | None = None,
    ) -> bool:
        """Refresh cached network diagnostics when due."""
        if self.network_refresh_callback is None:
            return False
        now = now or datetime.now(timezone.utc)
        if (
            not force
            and self._last_network_refresh is not None
            and now - self._last_network_refresh < NETWORK_REFRESH_INTERVAL
        ):
            return False

        try:
            network_data = await self.network_refresh_callback()
        except Exception:  # noqa: BLE001 - keep heating refresh stable on optional diagnostics failure.
            _LOGGER.debug("Network diagnostics refresh failed", exc_info=True)
            self._last_network_refresh = now
            return False

        if network_data:
            self.static_data.update(network_data)
            _LOGGER.debug(
                "Updated cached network diagnostics: keys=%s",
                sorted(network_data),
            )
        else:
            _LOGGER.debug("Network diagnostics refresh returned no values")
        self._last_network_refresh = now
        return bool(network_data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Weishaupt device."""
        await self.async_refresh_network_diagnostics()
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
        for register in self.experimental_wtc_registers:
            params.append(
                {
                    "key": register.key,
                    "mi": register.mi,
                    "mx": register.mx,
                    "ox": register.ox,
                    "os": register.os,
                    "vs": register.vs,
                }
            )
        for register in self.extended_experimental_wtc_registers:
            params.append(
                {
                    "key": register.key,
                    "mi": register.mi,
                    "mx": register.mx,
                    "ox": register.ox,
                    "os": register.os,
                    "vs": register.vs,
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

        return {**self.static_data, **results}
