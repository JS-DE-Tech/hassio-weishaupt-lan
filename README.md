# Weishaupt WTC - Home Assistant Integration

Custom Home Assistant integration for Weishaupt heating systems using the **CanApiJson** protocol (JSON over HTTP).

This integration communicates directly with the **Weishaupt Systemgerät (SG)** unit via the local network — no cloud required.

## Disclaimer

**Use at your own risk.**

This is an independent, community-developed integration with no affiliation to Weishaupt GmbH. Starting from v0.2.2 this integration can **write values to your heating device** — changing operating modes, triggering hot water cycles, and potentially other parameters.

While every effort is made to ensure correct and safe behaviour, the authors and contributors accept **no responsibility or liability** for any damage, malfunction, data loss, voided warranty, or any other consequence arising from the use of this integration. This includes but is not limited to unintended changes to device state, loss of heating or hot water, or damage to hardware.

**Always verify that any change made through this integration behaves as expected on your specific installation.**

## Supported Hardware

- **Weishaupt Systemgerät 2.5 / 2.6** (48301122172, 48301122242, 48301122512, 48301122522)
- Any Weishaupt heating system controlled through the Systemgerät (gas boilers, heat pumps, etc.)

## Prerequisites

1. The Weishaupt Systemgerät must be connected to your local network via RJ-45
2. JSON function must be enabled in the Systemgerät settings
3. You need the IP address of the Systemgerät (default hostname: `wem-sg`)
4. Default credentials: `admin` / `Admin123`

Test access by opening in your browser:
```
http://admin:Admin123@wem-sg/ajax/CanApiJson.json
```

## Installation

### HACS (Manual Repository)

1. Open HACS in Home Assistant
2. Go to Integrations → ⋮ (top right) → Custom repositories
3. Add this repository URL and select "Integration" as category
4. Install "Weishaupt WTC"
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/weishaupt_wtc` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Weishaupt WTC"
3. Enter the IP address (or hostname) of your Systemgerät
4. Optionally adjust username, password, scan interval, and the display names for heating circuits 1-3

The scan interval is configurable from **10 to 600 seconds** in 10 second steps.
The same value and the heating circuit names can be changed later from the
integration options. Saving options reloads the integration so the new polling
interval and names take effect without removing the integration.

Heating circuit names are display names only. Unique IDs, device identifiers and
CanApiJson addresses do not depend on these names.

## Sensors

The integration provides sensors across logical Home Assistant devices. HK1 and
warm water keep their existing technical CanApiJson keys and unique IDs, but are
shown as separate devices. External heating circuits are detected automatically
and only circuits that return a valid CanApiJson `CMD_RESPONSE` are added.
Optional module devices such as Solar are only created when setup-time probing
finds a plausible value rather than only missing responses or sentinel values.
When available, the read-only `/sd/systable.csv` inventory is checked first for
optional module detection. A missing Solar marker prevents Solar from being
created and allows stale integration-owned Solar devices to be cleaned up.

### Systemgerät (SG) — Modbus 100-155
- Betriebsart HK1 (Vorgabe / aktuell)
- So/Wi Umschaltung, Status HK1
- Raumsolltemperaturen (Komfort / Normal / Absenk / aktuell)
- Vorlaufsolltemperaturen (Komfort / Normal / Absenk / Sonderniveau / aktuell)
- Vorlaufisttemperatur, Plattenwärmetauschertemperatur
- Pufferspeicher Temperatur (oben / unten)
- Außentemperatur
- Systembetriebsart
- Wärmeanforderung (Heizung / Warmwasser)
- Warmwasser: Status, Push, Solltemperaturen, Ist-Temperatur, Zirkulation, Pumpe
- Kaskade: Folgewechsel, Abgleichtemperatur, Modulation, Sollwerte
- CANopen Fehler/Warnung Diagnoseblock (disabled by default)
- Uhrzeit und Datum

### WTC Kessel — Modbus 160-177
- Betriebsphase WTC und Brenner
- Vorlaufsolltemperatur, Kesseltemperatur, Rücklauftemperatur, Abgastemperatur
- Volumenstrom VPT, Anlagendruck

`wtc_abgastemperatur` (Modbus 167) and `wtc_ruecklauftemperatur` (Modbus 168)
are empirically confirmed on real hardware. Valid raw zero values are displayed
as measurements; only documented sentinel values such as `0x8000` and `0xFFFF`
are treated as unavailable.
- Wärmeleistung VPT
- Tageswärmemenge Vortag (Gesamt / Heizen / Warmwasser)

### Heizkreis (HK) — Modbus 1030-1046
- HK2 is the first external EM-HK module (`MI=0x02`, `MX=0x01`)
- HK3 is the second external EM-HK module (`MI=0x02`, `MX=0x02`)
- Betriebsart Vorgabe / aktuell
- So/Wi Umschaltung, Status
- Raumsolltemperaturen (Komfort / Normal / Absenk / aktuell)
- Vorlaufsolltemperaturen (Komfort / Normal / Absenk / Sonderniveau / aktuell)
- Vorlaufisttemperatur

HK1 now appears as its own logical Home Assistant device using the stable
`<entry_id>_hk1` device identifier. Its technical keys and CanApiJson addresses
remain unchanged (`MI=0x02`, `MX=0x00`). HK2 keeps the historic `hk_*` entity
keys and the `<entry_id>_hk` device identifier, because older releases exposed
one generic external heating circuit. HK3 uses separate `hk3_*` entity keys and
the `<entry_id>_hk3` device identifier.

### Warmwasser
- Status Warmwasser
- Warmwasser-Push button
- WW-Solltemperatur Normal slider: 50 to 60 °C in 1 °C steps
- WW-Solltemperatur Absenk slider: 8 to 60 °C in 1 °C steps
- WW-Solltemperatur aktuell
- Warmwassertemperatur
- Rücklauftemperatur Zirkulation
- Pumpe Warmwasser

No documented or clearly confirmed permanent warm-water enable/disable register
is currently known, so no permanent hot-water switch is created. The
`sg_warmwasser_push` register remains a separate one-shot push button and is
not used as an on/off switch.

## Writable controls

For each detected heating circuit the integration exposes a writable
**Betriebsart Vorgabe** select:

- Standby
- Zeitprogramm 1
- Zeitprogramm 2
- Zeitprogramm 3
- Sommer
- Komfort
- Normal
- Absenk

Writes are treated as successful only when the device returns a matching
CanApiJson `CMD_ACK`. Error responses, missing responses, normal read responses,
address mismatches and value mismatches are rejected. Write-capable entities
should still be used carefully: always verify the effect on your own heating
system after changing operating modes.

The system operating mode is exposed as a writable **Systembetriebsart** select
with the confirmed values Standby, Sommer and Automatik.

No documented or clearly confirmed writable warm-water operating-mode register
is currently known, so no warm-water operating-mode select is created.

### Solar (SOL) — Modbus 20-27
- Kollektortemperatur
- Speichertemperatur unten
- Solarertrag (Gesamtzähler / heute / Vortag)

Solar is only created when setup-time probing finds a plausible value. If all
known solar registers are missing or only return sentinel values such as
`0x8000` or `0xFFFF`, the Solar device and its entities are not created.

## Diagnostics

The repository includes a read-only helper at
`tools/dump_weishaupt_metadata.py`. Use it to download local web metadata files
when investigating unconfirmed warm-water on/off, warm-water mode, or
maintenance registers:

```powershell
$env:WEISHAUPT_PASSWORD = "Admin123"
python tools/dump_weishaupt_metadata.py --host 192.168.1.50 --output-dir weishaupt_metadata
```

The script only performs HTTP GET requests for `/script/einstellung.js`,
`/script/Form_eth_log.js` and `/sd/systable.csv`. It does not send write
commands. Maintenance data is not exposed through the currently documented
registers.

For confirmed runtime values, `tools/probe_weishaupt_registers.py` can read the
known HK, system and WTC registers. It only sends CanApiJson GET frames in
batches of up to six frames, never sends SET commands and never prints
credentials:

```powershell
$env:WEISHAUPT_PASSWORD = "Admin123"
python tools/probe_weishaupt_registers.py --host 192.168.1.50
```

## Protocol

This integration uses the Weishaupt CanApiJson protocol — a CAN bus-like protocol transmitted as JSON over HTTP POST requests to `/ajax/CanApiJson.json`.

Based on research from [BorgNumberOne/Weishaupt_CanApiJson](https://github.com/BorgNumberOne/Weishaupt_CanApiJson).

## License

MIT
