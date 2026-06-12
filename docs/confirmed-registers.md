# Confirmed Weishaupt CanApiJson Registers

This document lists CanApiJson registers that have been confirmed through real read-only responses on tested Weishaupt hardware.

The purpose of this file is to separate:

- confirmed registers that are safe to use in the Home Assistant integration
- empirically confirmed registers that are reliable on tested hardware but not fully documented upstream
- mirrored or ambiguous registers that must not yet be exposed as separate entities
- experimental candidates that still require correlation tests

## Safety and Protocol Notes

All values documented here were obtained using read-only CanApiJson requests.

```text
CM = 0x01  GET numeric value
```

No write commands were used for register discovery.

```text
CM = 0x03  SET numeric value
CM = 0x13  SET string value
```

Read requests should be sent in batches of no more than six frames.

```text
MAX_PARAMS_PER_REQUEST = 6
```

Testing on real hardware showed that larger mixed batches may return `CMD_ERROR` for later frames even when the same registers work correctly in smaller batches.

All CanApiJson HTTP requests should be serialized through one shared client
lock. The integration waits at least 300 ms between the completion of one HTTP
request and the start of the next request:

```text
MIN_REQUEST_GAP_SECONDS = 0.3
```

Writable entity updates are queued centrally in the coordinator. Rapid changes
are debounced for 750 ms, repeated pending writes to the same register keep only
the newest value, and writes to different registers are sent one at a time in
order. After the final acknowledged write, the integration waits 10 seconds
before requesting one full coordinator refresh:

```text
WRITE_DEBOUNCE_SECONDS = 0.75
POST_WRITE_SETTLE_SECONDS = 10
```

During pending writes and the post-write settling window, ordinary polling reads
are skipped and the last-good coordinator data is reused. Strictly acknowledged
configured target values may be reflected optimistically in coordinator data,
but actual-state mirrors must wait for a later real poll.

Dynamic read results are merged into a last-good cache. A transient failed or
empty batch must not remove previously valid values returned by an earlier
cycle. Network diagnostics keep their separate setup/reload path and 10-minute
refresh throttle.

Recommended polling intervals:

| Scenario | Recommendation |
|---|---:|
| Normal operation without experimental sensors | 30 seconds |
| Curated experimental sensors enabled | 60 seconds or slower |
| Extended experimental diagnostics enabled | 120 seconds or slower |

Valid raw zero values must be preserved as measurements.

Examples:

```text
0 l/h
0 kW
```

Only known sentinel values should be treated as unavailable:

```text
0x8000
0xFFFF
0x80000000
0xFFFFFFFF
```

## Register Format

The integration uses the following fields:

| Field | Meaning |
|---|---|
| `MI` | Module index |
| `MX` | Module instance |
| `OX` | Object index |
| `OS` | Object sub-index |
| `VS` | Value size in bytes |

Example request:

```text
01090126140200020000
```

Decoded:

| Field | Value |
|---|---|
| Command | `0x01` |
| MI | `0x09` |
| MX | `0x01` |
| OX | `0x2614` |
| OS | `0x02` |
| VS | `2` |

## Systemgerät Registers

| Key | Description | MI | MX | OX | OS | VS | Scaling / Mapping | Status |
|---|---|---:|---:|---:|---:|---:|---|---|
| `sg_systembetriebsart` | System operating mode | `0x01` | `0x00` | `0x261E` | `0x00` | `1` | `1=Standby`, `2=Summer`, `3=Automatic` | Confirmed |
| `sg_aussentemperatur` | Outdoor temperature | `0x01` | `0x00` | `0x26B1` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `sg_waermeanforderung_heizung` | Heating demand | `0x01` | `0x00` | `0x259C` | `0x01` | `2` | × `0.1 °C` | Confirmed |
| `sg_waermeanforderung_warmwasser` | Domestic-hot-water demand | `0x01` | `0x00` | `0x259D` | `0x01` | `2` | × `0.1 °C` | Confirmed |
| `sg_plattenwaermetauscher_b2` | Plate heat exchanger temperature | `0x01` | `0x00` | `0x261F` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `sg_pufferspeicher_oben` | Upper buffer-storage temperature | `0x01` | `0x00` | `0x2560` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `sg_pufferspeicher_unten` | Lower buffer-storage temperature | `0x01` | `0x00` | `0x2561` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `sg_canopen_diagnoseblock` | CANopen error/warning diagnostic block | `0x01` | `0x00` | `0x263F` | `0x00` | `8` | raw hex | Confirmed |

### System Operating Mode Mapping

| Raw value | Display value |
|---:|---|
| `1` | Standby |
| `2` | Summer |
| `3` | Automatic |

Confirmed real response:

```text
020100261e00000102
```

Decoded:

```text
raw = 2
System operating mode = Summer
```

## Heating-Circuit Registers

The same register structure is used for each heating circuit.

| Heating circuit | MI | MX |
|---|---:|---:|
| HK1 | `0x02` | `0x00` |
| HK2 | `0x02` | `0x01` |
| HK3 | `0x02` | `0x02` |

Observed display names from `/sd/systable.csv` on tested hardware:

| Heating circuit | Display name |
|---|---|
| HK1 | `Plattenwaermetauscher` |
| HK2 | `Fussbodenheizung` |
| HK3 | `Heizkoerper` |

The integration stores only the parsed detected-name mapping, not the complete
raw `systable.csv` file. Manual overrides are stored separately. Name resolution
uses non-empty manual override first, then the last successfully detected
mapping, then the generic `Heizkreis 1` / `Heizkreis 2` / `Heizkreis 3`
fallbacks. Display-name changes do not change entity unique IDs, device
identifiers, or register addresses.

The parser supports explicit HK markers, header/address metadata where
`MI=0x02` and `MX=0x00`, `0x01`, or `0x02`, and the real local metadata format
confirmed on the tested installation:

```text
M02_*.BIN;<display name>;<circuit number>
```

Only `M02_*.BIN` rows are interpreted as heating-circuit display names, and the
final column must be circuit number `1`, `2`, or `3`. This prevents the domestic
hot-water row `M03_*.BIN;Warmwasserspeicher;1` from being misclassified as HK1.

The real metadata also provides optional logical device display names:

| Module file | Logical device |
|---|---|
| `M01_*.BIN` | Systemgeraet |
| `M03_*.BIN` | Warmwasser |
| `M06_*.BIN` | Netzwerk |
| `M07_*.BIN` | WTC Kessel |

The historic HK2 technical key prefix `hk_` is intentionally retained for
backward compatibility with existing unique IDs, dashboards, and automations.

| Key suffix | Description | OX | OS | VS | Scaling / Mapping | Status |
|---|---|---:|---:|---:|---|---|
| `betriebsart_vorgabe` | Operating-mode target | `0x2533` | `0x02` | `1` | enum | Confirmed |
| `so_wi_umschaltung` | Summer/winter changeover | `0x2582` | `0x02` | `1` | boolean | Confirmed |
| `betriebsart_aktuell` | Current operating mode | `0x257E` | `0x04` | `1` | enum | Confirmed |
| `status` | Current heating-circuit status | `0x257E` | `0x05` | `1` | enum | Confirmed |
| `raumsoll_komfort` | Comfort room target temperature | `0x253B` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `raumsoll_normal` | Normal room target temperature | `0x253A` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `raumsoll_absenk` | Reduced room target temperature | `0x2539` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `raumsoll_aktuell` | Current room target temperature | `0x2558` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `vorlaufsoll_komfort` | Comfort flow target temperature | `0x256B` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `vorlaufsoll_normal` | Normal flow target temperature | `0x256A` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `vorlaufsoll_absenk` | Reduced flow target temperature | `0x2569` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `vorlaufsoll_sonderniveau` | Special-level flow target temperature | `0x252C` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `vorlaufsoll_aktuell` | Current flow target temperature | `0x2559` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `vorlaufisttemperatur` | Current flow temperature | `0x2507` | `0x02` | `2` | × `0.1 °C` | Confirmed |

### Heating-Circuit Target Operating Mode Mapping

| Raw value | Display value |
|---:|---|
| `1` | Standby |
| `2` | Time Program 1 |
| `3` | Time Program 2 |
| `4` | Time Program 3 |
| `5` | Summer |
| `6` | Comfort |
| `7` | Normal |
| `8` | Reduced |

Confirmed HK3 response:

```text
020202253302000102
```

Decoded:

```text
raw = 2
HK3 operating-mode target = Time Program 1
```

## Domestic-Hot-Water Registers

| Key | Description | MI | MX | OX | OS | VS | Scaling / Mapping | Status |
|---|---|---:|---:|---:|---:|---:|---|---|
| `sg_status_warmwasser` | Domestic-hot-water status | `0x03` | `0x00` | `0x2569` | `0x02` | `1` | enum | Confirmed |
| `sg_warmwasser_push` | One-shot domestic-hot-water push action | `0x03` | `0x00` | `0x2549` | `0x02` | `1` | boolean | Confirmed |
| `sg_ww_solltemperatur_normal` | Normal domestic-hot-water target temperature | `0x03` | `0x00` | `0x2539` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `sg_ww_solltemperatur_absenk` | Reduced domestic-hot-water target temperature | `0x03` | `0x00` | `0x2538` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `sg_ww_solltemperatur_aktuell` | Current domestic-hot-water target temperature | `0x03` | `0x00` | `0x252C` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `sg_warmwassertemperatur` | Current domestic-hot-water temperature | `0x03` | `0x00` | `0x2529` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `sg_ruecklauftemperatur_zirkulation` | Circulation return temperature | `0x03` | `0x00` | `0x2557` | `0x02` | `2` | × `0.1 °C` | Confirmed |
| `sg_pumpe_warmwasser` | Domestic-hot-water pump | `0x03` | `0x00` | `0x2551` | `0x02` | `1` | boolean | Confirmed |

A permanent domestic-hot-water enable/disable register has not yet been confirmed reliably. The one-shot push register must not be exposed as a permanent on/off switch.

## WTC Boiler Registers

| Key | Description | MI | MX | OX | OS | VS | Scaling / Mapping | Status |
|---|---|---:|---:|---:|---:|---:|---|---|
| `wtc_betriebsphase` | WTC operating phase | `0x09` | `0x01` | `0x2639` | `0x00` | `1` | enum | Confirmed |
| `wtc_brennerphase` | Burner operating phase | `0x07` | `0x00` | `0x2541` | `0x00` | `1` | enum | Confirmed |
| `wtc_vorlaufsolltemperatur` | Flow target temperature | `0x07` | `0x00` | `0x2545` | `0x00` | `2` | × `0.1 °C` | Confirmed |
| `wtc_kesseltemperatur` | Boiler temperature | `0x07` | `0x00` | `0x2532` | `0x00` | `2` | × `0.1 °C` | Confirmed |
| `wtc_abgastemperatur` | Flue-gas temperature | `0x07` | `0x00` | `0x2533` | `0x02` | `2` | × `0.1 °C` | Empirically confirmed |
| `wtc_ruecklauftemperatur` | Return temperature | `0x07` | `0x00` | `0x2537` | `0x00` | `2` | × `0.1 °C` | Empirically confirmed |
| `wtc_volumenstrom_vpt` | VPT volume flow | `0x09` | `0x01` | `0x2613` | `0x02` | `2` | `l/h` | Confirmed |
| `wtc_anlagendruck` | System pressure | `0x09` | `0x01` | `0x2614` | `0x02` | `2` | × `0.01 bar` | Confirmed |
| `wtc_waermeleistung_vpt` | VPT thermal output | `0x09` | `0x01` | `0x2631` | `0x02` | device-dependent response size | × `0.01 kW` | Confirmed |
| `wtc_tageswaermemenge_vortag_heizen` | Previous-day heat quantity: heating | `0x09` | `0x01` | `0x2626` | `0x02` | `4` | × `0.01 kWh` | Confirmed |
| `wtc_tageswaermemenge_vortag_warmwasser` | Previous-day heat quantity: domestic hot water | `0x09` | `0x01` | `0x2627` | `0x02` | `4` | × `0.01 kWh` | Confirmed |
| `wtc_tageswaermemenge_vortag_gesamt` | Previous-day heat quantity: total | `0x09` | `0x01` | `0x2628` | `0x02` | `4` | × `0.01 kWh` | Confirmed |
| `wtc_zeit_bis_wartung` | Remaining time until maintenance | `0x09` | `0x01` | `0x2641` | `0x00` | `2` | `h` | Empirically confirmed |
| `wtc_wartungsintervall` | Maintenance interval | `0x09` | `0x01` | `0x2642` | `0x00` | `2` | `h` | Empirically confirmed |
| `wtc_brennerstarts_gesamt` | Burner starts total | `0x09` | `0x01` | `0x2920` | `0x00` | `2` | count | Empirically confirmed |
| `wtc_betriebsstunden_gesamt` | Burner operating hours total | `0x09` | `0x01` | `0x2921` | `0x00` | `2` | `h` | Empirically confirmed |

`wtc_waermeleistung_vpt` is probed with `VS=4` first and `VS=2` as a fallback.
Both sizes use the same confirmed address and preserve raw `0` as valid
`0.0 kW`.

The maintenance values were correlated against a real installation display
showing roughly `4997 h` remaining and a `5000 h` interval. They are read-only
diagnostics only; the integration does not expose reset or write operations for
maintenance.

### Confirmed Real WTC Responses

| Description | Request | Response | Decoded |
|---|---|---|---|
| System pressure | `01090126140200020000` | `02090126140200020095` | `1.49 bar` |
| Boiler temperature | `01070025320000020000` | `02070025320000020192` | `40.2 °C` |
| VPT volume flow | `01090126130200020000` | `02090126130200020000` | `0 l/h` |
| Flue-gas temperature | `01070025330200020000` | `0207002533020002018f` | `39.9 °C` |
| Return temperature | `01070025370000020000` | `0207002537000002019d` | `41.3 °C` |
| Flow target temperature | `01070025450000020000` | `02070025450000020050` | `8.0 °C` |

## Mirrored Counter Registers

The total-counter values were observed at multiple mirrored register addresses.

### Burner Starts

| MI | MX | OX | OS | Observed value |
|---:|---:|---:|---:|---:|
| `0x09` | `0x01` | `0x2901` | `0x00` | `31261` |
| `0x09` | `0x01` | `0x2920` | `0x00` | `31261` |
| `0x07` | `0x00` | `0x2A01` | `0x00` | `31261` |
| `0x07` | `0x00` | `0x2A20` | `0x00` | `31261` |

### Burner Operating Hours

| MI | MX | OX | OS | Observed value |
|---:|---:|---:|---:|---:|
| `0x09` | `0x01` | `0x2900` | `0x00` | `5604` |
| `0x09` | `0x01` | `0x2921` | `0x00` | `5604` |
| `0x07` | `0x00` | `0x2A00` | `0x00` | `5604` |
| `0x07` | `0x00` | `0x2A21` | `0x00` | `5604` |

The tested portal displayed resettable and lifetime counters with identical values. Therefore, the exact distinction between the mirrored addresses still requires additional verification.

The integration should currently use only:

```text
Burner starts total:
MI = 0x09
MX = 0x01
OX = 0x2920
OS = 0x00
VS = 2

Burner operating hours total:
MI = 0x09
MX = 0x01
OX = 0x2921
OS = 0x00
VS = 2
```

## Optional Experimental WTC Diagnostics

When the integration option `Enable experimental read-only WTC sensors` is
enabled, setup probes the following curated WTC candidates. Candidates that
return `CMD_RESPONSE` are exposed on the separate `WTC Experimental Diagnostics`
device. Candidates that return `CMD_ERROR` are skipped.

These values are intentionally raw diagnostics for correlation testing. They do
not have confirmed meanings, units, device classes, state classes, or write
support.

| Address | VS | Notes |
|---|---:|---|
| `09/01/2610/02` | `2` | Candidate temperature-related WTC value, probable scale `0.1 C` |
| `09/01/2611/02` | `2` | Candidate temperature-related WTC value, probable scale `0.1 C` |
| `09/01/2612/02` | `2` | Candidate temperature-related WTC value, probable scale `0.1 C` |
| `09/01/2615/02` | `2` | Probable VPT flow temperature, probable scale `0.1 C` |
| `09/01/2619/02` | `1` | Probable internal pump modulation, probable unit `%` |
| `09/01/263A/02` | `2` | Curated experimental candidate |
| `09/01/2679/00` | `2` | Curated experimental candidate |
| `09/01/268A/00` | `4` | Curated experimental candidate |
| `09/01/268B/00` | `4` | Curated experimental candidate |
| `09/01/268C/00` | `4` | Curated experimental candidate |
| `09/01/268D/00` | `2` | Curated experimental candidate |
| `09/01/268E/00` | `2` | Curated experimental candidate |
| `09/01/268F/00` | `2` | Curated experimental candidate |
| `09/01/2902/00` | `2` | Curated experimental candidate |
| `09/01/2903/00` | `2` | Curated experimental candidate |
| `09/01/2904/00` | `1` | Curated experimental candidate |
| `09/01/2905/00` | `1` | Curated experimental candidate |
| `09/01/2908/00` | `2` | Curated experimental candidate |
| `09/01/2922/00` | `1` | Curated experimental candidate |

Experimental entities keep the primary state as the raw signed integer. Hints,
confidence, probable unit, and probable scale are exposed only as attributes
until the register meaning is confirmed.

Raw experimental `0` or `1` values are not automatically classified as binary
states. Confirmed binary/state-like values can keep explicit mappings such as
`Ein` / `Aus`, but unconfirmed candidates remain raw diagnostics.

### Extended Experimental Catalog

The option `Enable extended experimental read-only WTC sensors` adds
infrastructure for a capped second catalog under the same `WTC Experimental
Diagnostics` device. The catalog is disabled by default, is only evaluated when
curated experimental sensors are enabled, and is capped at 100 explicitly listed
addresses.

Current catalog: empty.

Reason: the committed discovery artifacts contain broad scan outputs and
candidate hits, but not a reviewed semantic list that safely excludes mirrors,
static tables, network values, already confirmed regular sensors, and existing
curated experimental entries. A curated correlation artifact with address,
observed values over time, suspected meaning, and exclusion rationale is needed
before populating this list.

## Network Diagnostic Registers

These values were confirmed through the local web-interface JavaScript and read-only requests.

| Description | MI | MX | OX | OS | VS | Scaling / Mapping |
|---|---:|---:|---:|---:|---:|---|
| IP mode | `0x06` | `0x00` | `0x2507` | `0x00` | `1` | `1` = Manuell, `3` = Automatisch (DHCP) |
| IP address | `0x06` | `0x00` | `0x2508` | `0x00` | `4` | IPv4 |
| Subnet mask | `0x06` | `0x00` | `0x2509` | `0x00` | `4` | IPv4 |
| Gateway | `0x06` | `0x00` | `0x250A` | `0x00` | `4` | IPv4 |
| DNS server | `0x06` | `0x00` | `0x250B` | `0x00` | `4` | IPv4 |
| MAC component 1 | `0x06` | `0x00` | `0x250C` | `0x01` | `2` | derived MAC byte |
| MAC component 2 | `0x06` | `0x00` | `0x250C` | `0x02` | `2` | derived MAC byte |
| MAC component 3 | `0x06` | `0x00` | `0x250C` | `0x03` | `2` | derived MAC byte |
| MAC component 4 | `0x06` | `0x00` | `0x250C` | `0x04` | `2` | derived MAC byte |
| MAC component 5 | `0x06` | `0x00` | `0x250C` | `0x05` | `2` | derived MAC byte |
| MAC component 6 | `0x06` | `0x00` | `0x250C` | `0x06` | `2` | derived MAC byte |
| Gerätename / NBNS | `0x06` | `0x00` | `0x250E` | `0x00` | `16` | string GETS |
| Zertifikat-CN | `0x06` | `0x00` | `0x2511` | `0x00` | `50` | string GETS |

The configured network device name is probed with the protocol string-read
command at `06/00/250E/00 VS=16 GETS` and exposed as `Gerätename` only when the
device returns a non-empty supported string response. `06/00/2505/00` is a web
UI write address and is not used.

`Zertifikat-CN` is probed with `06/00/2511/00 VS=50 GETS` and is also skipped
safely when unsupported or empty.

The six MAC components are probed during setup/reload and during the throttled
network-diagnostics synchronization. The integration exposes one derived
`MAC-Adresse` diagnostic in `XX-XX-XX-XX-XX-XX` format and does not create
visible component entities. If any component is missing or invalid during the
initial read, the derived MAC entity is skipped safely. If a later refresh fails,
the last successful MAC value is retained.

Network diagnostics are read immediately on setup or reload, then synchronized
at most once every 10 minutes outside the ordinary heating-system polling batch.
Successful values are merged into cached coordinator data; missing optional
values do not remove previous visible states. No network write support,
password-related registers, usernames, cookies, Authorization headers, or tokens
are exposed.

The logical network device keeps the stable `<entry_id>_network` identifier and
the display name `Weishaupt Systemgeraet Netzwerk`. Its Home Assistant device
info includes the local configuration URL `http://<configured-host>/` without
credentials.

## Derived Device Date and Time

The integration derives separate diagnostic date and clock-time sensors from
the existing raw Systemgeraet components:

| Derived key | Source components | Format |
|---|---|---|
| `sg_device_date` | `sg_datum_tag`, `sg_datum_monat`, `sg_datum_jahr` | `DD.MM.YYYY` |
| `sg_device_clock_time` | `sg_uhrzeit_stunden`, `sg_uhrzeit_minuten` | `HH:MM` |

Validated date field order on tested hardware:

| Raw component key | Address | Meaning |
|---|---|---|
| `sg_datum_jahr` | `01/00/2563/02` | year offset, for example `26` -> `2026` |
| `sg_datum_monat` | `01/00/2563/03` | month |
| `sg_datum_tag` | `01/00/2563/04` | day |

No extra protocol reads are added for these derived sensors. `sg_device_date`
and `sg_device_clock_time` are enabled by default. The raw component entities
and the backward-compatible combined timestamp remain available as diagnostic
entities and are disabled by default.

## System Operating-Mode Mirror

`sg_systembetriebsart_aktuell` is a read-only mirror of the confirmed
`sg_systembetriebsart` coordinator data. It exposes the same decoded mapping and
does not add another protocol read.

## Snapshot Export Workflow

The service `weishaupt_wtc_lan.export_experimental_snapshot` writes one JSON
and one CSV file under `/config/weishaupt_wtc_lan_diagnostics/`.

Snapshots include timestamp, integration version, host identifier without
credentials, regular WTC values, network diagnostics when available, curated
experimental values, and extended experimental values when enabled. They do not
export passwords, authorization headers, HTTP Basic credentials, tokens, or
cookies.

## Local Metadata Export Workflow

The service `weishaupt_wtc_lan.export_local_metadata` writes timestamped
read-only local metadata under
`/config/weishaupt_wtc_lan_diagnostics/local_metadata/`.

The export includes `/sd/systable.csv` when it can be fetched and a JSON summary
with parsed names, persisted detected names, whether detected-name usage is
enabled, and resolved display names. It excludes passwords, authorization
headers, tokens, cookies, and HTTP credentials.

## Broad Experimental Candidates

The following broad discovery topics are intentionally not exposed as regular
Home Assistant entities.

Their meaning, scaling, stability, or mirrored-register behavior still requires targeted correlation testing.

### System and Heating Circuits

- outdoor-temperature minimum and maximum
- outdoor-temperature reset
- damped and mixed outdoor temperature
- per-circuit heating demand
- heating-curve slope
- parallel shift
- minimum and maximum flow limits
- pump state
- mixer target and actual position
- optimization correction values
- party and heating-pause parameters
- holiday parameters
- screed-program parameters

### Domestic Hot Water

- permanent enable/disable
- writable operating mode
- loading strategy
- switching differential
- maximum loading time
- legionella-protection configuration
- solar loading shutdown threshold

### WTC / WE0

- resettable burner-start counter
- resettable burner operating-hours counter
- maintenance dates and maintenance intervals
- pump modulation
- pump electrical power
- internal three-way valve state
- ionization-signal values
- gas-valve offset and control values
- flame-formation time
- fan speed and fan-control values
- gas pressure
- decoded fault-memory values

## Source and Research References

Protocol research and initial register documentation:

```text
https://github.com/BorgNumberOne/Weishaupt_CanApiJson
```

Original Home Assistant integration:

```text
https://github.com/kraiz/hassio-weishaupt
```

This fork extends the original integration with additional device separation, reliability fixes, confirmed WTC values, and bundled read-only discovery tools.

