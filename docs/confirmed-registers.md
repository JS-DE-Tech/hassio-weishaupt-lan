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
| `wtc_brennerstarts_gesamt` | Burner starts total | `0x09` | `0x01` | `0x2920` | `0x00` | `2` | count | Empirically confirmed |
| `wtc_betriebsstunden_gesamt` | Burner operating hours total | `0x09` | `0x01` | `0x2921` | `0x00` | `2` | `h` | Empirically confirmed |

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
| `09/01/2610/02` | `2` | Curated experimental candidate |
| `09/01/2611/02` | `2` | Curated experimental candidate |
| `09/01/2612/02` | `2` | Curated experimental candidate |
| `09/01/2615/02` | `2` | Curated experimental candidate |
| `09/01/2619/02` | `1` | Curated experimental candidate |
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

## Network Diagnostic Registers

These values were confirmed through the local web-interface JavaScript and read-only requests.

| Description | MI | MX | OX | OS | VS | Scaling / Mapping |
|---|---:|---:|---:|---:|---:|---|
| IP mode | `0x06` | `0x00` | `0x2507` | `0x00` | `1` | enum |
| IP address | `0x06` | `0x00` | `0x2508` | `0x00` | `4` | IPv4 |
| Subnet mask | `0x06` | `0x00` | `0x2509` | `0x00` | `4` | IPv4 |
| Gateway | `0x06` | `0x00` | `0x250A` | `0x00` | `4` | IPv4 |
| DNS server | `0x06` | `0x00` | `0x250B` | `0x00` | `4` | IPv4 |

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

