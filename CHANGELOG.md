# Changelog

## 0.4.0.1 - 2026-06-10

- Fix: Limit automatic CanApiJson read batches to six VG frames and keep dense `N01`, `N02`, ... numbering in every batch.
- Fix: Treat raw value `0` as a valid measurement value, including WTC volume flow.
- Fix: Ensure `HK3 Betriebsart Vorgabe` and `Systembetriebsart` selects read their current state directly from `coordinator.data`.
- Fix: Keep HK1, HK2 and HK3 current operating-mode and status sensors while exposing only writable Vorgabe registers as controls.
- Fix: Use `/sd/systable.csv` as the primary read-only module inventory for optional device groups and avoid creating Solar when the module is missing.
- Feature: Add read-only `tools/probe_weishaupt_registers.py` for the empirically confirmed HK, system and WTC registers.
- Note: WTC registers 167 (`wtc_abgastemperatur`) and 168 (`wtc_ruecklauftemperatur`) are empirically confirmed.
- Note: No permanent warm-water on/off switch is created; `sg_warmwasser_push` remains a one-shot button only.

## 0.4.0 - 2026-06-09

- Feature: Move HK1 entities to a separate logical Home Assistant device while preserving their existing keys, CanApiJson addresses and unique IDs.
- Feature: Move warm-water entities and the existing Warmwasser-Push button to a separate `Weishaupt Warmwasser` device.
- Feature: Add writable `Systembetriebsart` select for Standby, Sommer and Automatik.
- Feature: Add Number slider entities for `WW-Solltemperatur Normal` (50-60 °C) and `WW-Solltemperatur Absenk` (8-60 °C), using the existing confirmed temperature registers.
- Feature: Register the Number platform and extend the scan interval slider to 10-600 seconds in 10 second steps.
- Feature: Detect optional WTC, warm-water and solar groups during setup/reload; Solar is not created when its known registers are missing or only return sentinel values.
- Feature: Add read-only `tools/dump_weishaupt_metadata.py` for local metadata inspection when investigating unconfirmed warm-water or maintenance registers.
- Fix: Reject write ACKs that contain an unexpected value payload.
- Migration: HK1 now uses the stable `<entry_id>_hk1` device identifier. Warm-water uses `<entry_id>_ww`. Existing entity unique IDs remain based on the original technical keys.
- Note: No clearly confirmed permanent warm-water on/off register or warm-water operating-mode register was found, so no Switch or additional WW operating-mode Select is created. Maintenance data is not available through the currently documented registers.
- Note: `wtc_abgastemperatur` remains on the WTC device and continues to treat `0x8000` and `0xFFFF` as unavailable.

## 0.3.0 - 2026-06-09

- Feature: Detect external EM-HK heating circuits dynamically and support HK1, HK2 and HK3 without creating entities for circuits that do not answer the CanApiJson probe.
- Feature: Add writable Betriebsart Vorgabe selects for every detected heating circuit.
- Feature: Add configurable heating circuit display names and an options flow with automatic reload.
- Feature: Replace the scan interval number field with a Home Assistant slider from 30 to 300 seconds in 10 second steps.
- Fix: Accept write operations only after a matching CanApiJson `CMD_ACK`; `CMD_ERROR`, missing responses and `CMD_RESPONSE` are rejected.
- Migration: HK2 keeps the historical `hk_*` sensor keys and `<entry_id>_hk` device identifier. HK3 uses new `hk3_*` keys and `<entry_id>_hk3`.

## 0.2.5 - 2026-04-19

- Fix: Make device timestamp timezone-aware (UTC) to fix auto-update of sensor values (#5, thanks @wagnerpizza).

## 0.2.3 - 2026-04-04

- Fix: Add missing `device_info` to `WeishauptSelectEntity` so the Select is visible in the HA device view.
- Feature: Add Button platform with `Warmwasser-Push` button (Register 131) that writes value 1 to trigger a domestic hot water push cycle.

## 0.2.2 - 2026-03-30

- Feature: Add writable Select for `sg_betriebsart_hk1_vorgabe` (Register 100) to allow changing Heizkreis 1 Betriebsart (#4).
- Feature: Add API write support for CanApiJson SET frames so writable registers can be updated from HA.

## 0.2.1 - 2026-03-21

- Fix: Create the SG system device explicitly so child devices reference a valid `via_device` parent and avoid upcoming Home Assistant registry breakage.
- Test: Add regression coverage for the SG root device and child device hierarchy.

## 0.2.0 - 2026-03-21

- Feature: Re-add the documented HK and SOL sensor groups from the PDF register map, restoring Heizkreis and Solar entities.
- Feature: Add the documented SG fault block diagnostics from Modbus 120-123 as disabled-by-default diagnostic sensors.
- Fix: Restore the documented SG time/date component registers so the consolidated `sg_device_time` sensor is populated correctly.
- Fix: Poll only real device frames and derive synthetic sensors from the fetched source frames.
- Fix: Guard against empty device responses and log a warning instead of failing with a `NoneType` error during coordinator refresh (#2).

## 0.1.3 - 2026-02-27

- Feature: Added logo.

## 0.1.2 - 2026-02-27

- Fix: sensor amount in README.md was outdated after removing HK and SOL device groups. Updated to reflect current sensor count (50).
- Fix: update manifest version to 0.1.2 for latest release.

## 0.1.1 - 2026-02-27

- Breaking: Drop `HK_SENSORS` and `SOL_SENSORS` from the integration (these device groups will no longer be registered by default). This reduces entity count and focuses the integration on `SG` and `WTC` device groups.

## 0.0.8 - 2026-02-27

- Release: prepare and publish v0.0.8 (includes latest fixes).

## 0.0.7 - 2026-02-27

- Reverted the parent device change from 0.0.5.

## 0.0.6 - 2026-02-27

- Release: prepare and publish v0.0.6 (bugfixes and registry fixes).

## 0.0.5 - 2026-02-27

- Fix: create parent device so `via_device` references are valid and avoid registry warnings.


## 0.0.4 - 2026-02-27

- Fix: Treat sentinel raw values (0x8000/0xFFFF) as unavailable so sensors don't report extreme negative temperatures.

## 0.0.3 - 2026-02-27

- Consolidate WEM Systemgerät diagnostic time/date registers into a single `Uhrzeit / Datum` (`sg_device_time`) timestamp sensor.
- Remove the separate `Uhrzeit (Stunden)`, `Uhrzeit (Minuten)`, `Datum (Tag)`, `Datum (Monat)`, and `Datum (Jahr)` sensors.
- Diagnostic sensors remain disabled by default.

## 0.0.2

- Previous changes.
