"""DataUpdateCoordinator for Weishaupt WTC."""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    WeishauptApiClient,
    WeishauptApiError,
    WeishauptConnectionError,
)
from .const import CMD_RESPONSE
from .const import DOMAIN
from .heating_circuits import build_polled_sensor_definitions
from .sensors import ExperimentalWtcRegister, WeishauptSensorDefinition

_LOGGER = logging.getLogger(__name__)

NETWORK_REFRESH_INTERVAL = timedelta(minutes=10)
WRITE_DEBOUNCE_SECONDS = 0.75
POST_WRITE_SETTLE_SECONDS = 10

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


@dataclass(frozen=True)
class _QueuedWrite:
    """One queued writable target update."""

    key: str
    mi: int
    mx: int
    ox: int
    os: int
    vs: int
    value_int: int

    @property
    def address(self) -> tuple[int, int, int, int, int]:
        """Return the register-address tuple used for queue coalescing."""
        return (self.mi, self.mx, self.ox, self.os, self.vs)


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
        self._last_good_dynamic_data: dict[str, Any] = {}
        self._write_lock = asyncio.Lock()
        self._write_queue: OrderedDict[
            tuple[int, int, int, int, int], _QueuedWrite
        ] = OrderedDict()
        self._writes_in_flight = 0
        self._write_drain_active = False
        self._write_debounce_task: asyncio.Task | None = None
        self._post_write_refresh_task: asyncio.Task | None = None

    async def async_enqueue_write(
        self,
        sensor_def: WeishauptSensorDefinition,
        value_int: int,
    ) -> None:
        """Queue a writable target update for debounced serialized delivery."""
        queued = _QueuedWrite(
            key=sensor_def.key,
            mi=sensor_def.mi,
            mx=sensor_def.mx,
            ox=sensor_def.ox,
            os=sensor_def.os,
            vs=sensor_def.vs,
            value_int=value_int,
        )
        async with self._write_lock:
            self._write_queue[queued.address] = queued
            self._cancel_post_write_refresh_locked()
            self._schedule_write_debounce_locked()

    def _schedule_write_debounce_locked(self) -> None:
        """Schedule or reset the short write debounce task."""
        if self._write_drain_active:
            return
        if self._write_debounce_task is not None and not self._write_debounce_task.done():
            self._write_debounce_task.cancel()
        self._write_debounce_task = asyncio.create_task(
            self._async_flush_write_queue_after_debounce()
        )

    def _cancel_post_write_refresh_locked(self) -> None:
        """Cancel a pending delayed post-write refresh."""
        if (
            self._post_write_refresh_task is not None
            and not self._post_write_refresh_task.done()
        ):
            self._post_write_refresh_task.cancel()
        self._post_write_refresh_task = None

    async def _async_flush_write_queue_after_debounce(self) -> None:
        """Wait for coalescing, then drain queued writes one at a time."""
        try:
            await asyncio.sleep(WRITE_DEBOUNCE_SECONDS)
            async with self._write_lock:
                self._write_drain_active = True
            await self._async_drain_write_queue()
        except asyncio.CancelledError:
            raise

    async def _async_drain_write_queue(self) -> None:
        """Send queued writes serially and schedule one delayed refresh."""
        while True:
            async with self._write_lock:
                if not self._write_queue:
                    self._write_debounce_task = None
                    self._write_drain_active = False
                    self._schedule_post_write_refresh_locked()
                    return
                _, queued = self._write_queue.popitem(last=False)
                self._writes_in_flight += 1

            success = False
            try:
                success = await self.client.write_parameter(
                    mi=queued.mi,
                    mx=queued.mx,
                    ox=queued.ox,
                    os_val=queued.os,
                    vs=queued.vs,
                    value_int=queued.value_int,
                )
            except Exception:  # noqa: BLE001 - write failures must not crash HA updates.
                _LOGGER.warning(
                    "Queued write failed for key=%s MI=0x%02x MX=0x%02x OX=0x%04x",
                    queued.key,
                    queued.mi,
                    queued.mx,
                    queued.ox,
                    exc_info=True,
                )
            else:
                if success:
                    self._apply_acknowledged_target_value(queued)
                else:
                    _LOGGER.warning(
                        "Queued write was not acknowledged for key=%s MI=0x%02x MX=0x%02x OX=0x%04x",
                        queued.key,
                        queued.mi,
                        queued.mx,
                        queued.ox,
                    )
            finally:
                async with self._write_lock:
                    self._writes_in_flight -= 1
                    if self._write_queue:
                        self._cancel_post_write_refresh_locked()
                    else:
                        self._schedule_post_write_refresh_locked()

    def _schedule_post_write_refresh_locked(self) -> None:
        """Schedule exactly one quiet-period refresh after the last write."""
        if (
            self._post_write_refresh_task is not None
            and not self._post_write_refresh_task.done()
        ):
            self._post_write_refresh_task.cancel()
        self._post_write_refresh_task = asyncio.create_task(
            self._async_request_refresh_after_write_settle()
        )

    async def _async_request_refresh_after_write_settle(self) -> None:
        """Request one coordinator refresh after the post-write quiet period."""
        try:
            await asyncio.sleep(POST_WRITE_SETTLE_SECONDS)
        except asyncio.CancelledError:
            raise

        async with self._write_lock:
            if asyncio.current_task() is self._post_write_refresh_task:
                self._post_write_refresh_task = None

        refresh = getattr(self, "async_request_refresh", None)
        if refresh is not None:
            await refresh()

    def _apply_acknowledged_target_value(self, queued: _QueuedWrite) -> None:
        """Update coordinator data optimistically after a strictly validated ACK."""
        value_hex = f"{queued.value_int:0{queued.vs * 2}x}"
        data = {
            "vg": (
                f"{CMD_RESPONSE:02x}{queued.mi:02x}{queued.mx:02x}"
                f"{queued.ox:04x}{queued.os:02x}{queued.vs:04x}{value_hex}"
            ),
            "cmd": CMD_RESPONSE,
            "mi": queued.mi,
            "mx": queued.mx,
            "ox": queued.ox,
            "os": queued.os,
            "vs": queued.vs,
            "value_hex": value_hex,
            "value_int": queued.value_int,
        }
        self._last_good_dynamic_data[queued.key] = data
        updated = {**(getattr(self, "data", None) or {}), queued.key: data}
        set_updated_data = getattr(self, "async_set_updated_data", None)
        if set_updated_data is not None:
            set_updated_data(updated)
        else:
            self.data = updated

    async def _writes_pending_or_settling(self) -> bool:
        """Return True when polling should yield cached data instead of reading."""
        async with self._write_lock:
            return (
                bool(self._write_queue)
                or self._writes_in_flight > 0
                or self._write_drain_active
                or (
                    self._write_debounce_task is not None
                    and not self._write_debounce_task.done()
                )
                or (
                    self._post_write_refresh_task is not None
                    and not self._post_write_refresh_task.done()
                )
            )

    def _cached_data(self) -> dict[str, Any]:
        """Return static data plus the last good dynamic values."""
        if self._last_good_dynamic_data:
            return {**self.static_data, **self._last_good_dynamic_data}
        return dict(getattr(self, "data", None) or self.static_data)

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
        if await self._writes_pending_or_settling():
            _LOGGER.debug(
                "Skipping coordinator poll while writes are pending or settling"
            )
            return self._cached_data()

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

        failed_batches = getattr(self.client, "last_read_failed_batches", 0)
        if failed_batches:
            _LOGGER.warning(
                "Weishaupt refresh completed with %s failed read batch(es); retaining last good values where available",
                failed_batches,
            )
        self._last_good_dynamic_data.update(results)

        definitions_by_key = {
            sensor_def.key: sensor_def for sensor_def in self.polled_sensor_definitions
        }
        for key in DEBUG_STATE_KEYS:
            sensor_def = definitions_by_key.get(key)
            if sensor_def is None:
                continue
            data = self._last_good_dynamic_data.get(key)
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

        return {**self.static_data, **self._last_good_dynamic_data}
