# Changelog

## Unreleased

### Added
- Added total burner-start counter for the WTC boiler.
- Added total burner operating-hours counter for the WTC boiler.
- Added optional read-only `WTC Experimental Diagnostics` device.
- Added selected raw WTC register candidates for real-hardware correlation testing.
- Added diagnostic attributes with raw and scaled values.

### Changed
- Kept CanApiJson read batches limited to six frames for improved reliability.
- Kept experimental polling disabled by default.

### Fixed
- Preserved valid raw zero values in regular and experimental read paths.
- Ensured that a failing experimental register does not discard valid values from the same batch.

## 0.4.1 - 2026-06-10

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
