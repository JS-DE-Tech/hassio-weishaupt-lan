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

The scan interval is configurable from **30 to 300 seconds** in 10 second steps.
The same value and the heating circuit names can be changed later from the
integration options. Saving options reloads the integration so the new polling
interval and names take effect without removing the integration.

Heating circuit names are display names only. Unique IDs, device identifiers and
CanApiJson addresses do not depend on these names.

## Sensors

The integration provides sensors across these device groups. External heating
circuits are detected automatically and only circuits that return a valid
CanApiJson `CMD_RESPONSE` are added.

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

HK1 remains part of the system device for compatibility. HK2 keeps the historic
`hk_*` entity keys and the `<entry_id>_hk` device identifier, because older
releases exposed one generic external heating circuit. HK3 uses separate
`hk3_*` entity keys and the `<entry_id>_hk3` device identifier.

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
CanApiJson `CMD_ACK`. Error responses, missing responses, and normal read
responses are rejected. Write-capable entities should still be used carefully:
always verify the effect on your own heating system after changing operating
modes.

### Solar (SOL) — Modbus 20-27
- Kollektortemperatur
- Speichertemperatur unten
- Solarertrag (Gesamtzähler / heute / Vortag)

## Protocol

This integration uses the Weishaupt CanApiJson protocol — a CAN bus-like protocol transmitted as JSON over HTTP POST requests to `/ajax/CanApiJson.json`.

Based on research from [BorgNumberOne/Weishaupt_CanApiJson](https://github.com/BorgNumberOne/Weishaupt_CanApiJson).

## License

MIT
