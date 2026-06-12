# Weishaupt WTC LAN for Home Assistant

<p align="left">
  <img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/system.png"
       alt="Weishaupt WTC heating system"
       width="620">
</p>

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-41BDF5?logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom%20Repository-41BDF5)](https://hacs.xyz/)
[![Protocol](https://img.shields.io/badge/protocol-local%20CanApiJson-success)](#protocol)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](https://github.com/JS-DE-Tech/hacs-weishaupt-lan/blob/main/LICENSE)
[![Support via PayPal](https://img.shields.io/badge/Support%20via-PayPal-0070BA?logo=paypal&logoColor=white)](https://paypal.me/JensSaffrich)

Local Home Assistant integration for Weishaupt heating systems. The integration
communicates directly with the Weishaupt system device (SG) over the local LAN
and reads heating data through the CanApiJson JSON interface. No cloud
connection is required.

> [!WARNING]
> Use this integration at your own risk. Some entities can write values to the heating system. Always verify changes directly on your installation.

## Disclaimer

This is an independent, community-developed integration with no affiliation to Weishaupt GmbH.

Starting with version `v0.3.0`, the integration can write selected values to the heating system, including operating modes and domestic-hot-water actions. Incorrect values or unexpected device behavior may cause loss of heating, loss of hot water, malfunction, or other damage.

The authors and contributors accept no responsibility or liability for damage, malfunction, data loss, voided warranty, or any other consequence arising from the use of this integration.

## Supported Hardware

Tested and intended for:

- Weishaupt Systemgerät 2.5 / 2.6
- Article numbers: `48301122172`, `48301122242`, `48301122512`, `48301122522`
- Heating systems controlled through the Weishaupt Systemgerät, including WTC gas boilers and installations with additional heating-circuit modules

Other installations may work, but register availability depends on the installed modules and firmware.

## Prerequisites

1. Connect the Weishaupt Systemgerät to the local network using RJ-45.
2. Enable the JSON interface in the Systemgerät settings. **
3. Determine the IP address or hostname of the Systemgerät.
4. Use the configured HTTP Basic Authentication credentials.

Default values on many installations:

```text
Hostname: wem-sg
Username: admin
Password: Admin123
```

Example test URL:

```text
http://admin:Admin123@wem-sg/ajax/CanApiJson.json
```

> [!IMPORTANT]
> To use this integration, the WEM Portal connection must be disabled. The Weishaupt Systemgerät does not allow simultaneous use of the WEM Portal cloud service and the local CanApiJson interface.

### **Enable the JSON Interface

The CanApiJson interface is disabled by default on many installations and must be enabled directly on the Weishaupt Systemgerät.

#### Step 1 — Open the service menu

From the home screen, navigate to the service menu (wrench icon).

<img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/enable_json_01.png" width="400">

Select the installer/service level.

<img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/enable_json_02.png" width="400">

#### Step 2 — Log in as installer

Enter the installer password.

<img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/enable_json_03.png" width="400">

After successful login, the installer menu will be displayed.

<img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/enable_json_04.png" width="400">

#### Step 3 — Open commissioning settings

Select **Commissioning**.

<img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/enable_json_05.png" width="400">

Navigate to **Network**.

<img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/enable_json_06.png" width="400">

#### Step 4 — Enable the JSON interface

Open **JSON Interface**.

<img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/enable_json_07.png" width="400">

Set **JSON Interface** to **On**.

<img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/enable_json_08.png" width="400">

The JSON interface is now enabled.

#### Step 5 — Disable WEM Portal

Return to the user settings menu.

Open **Settings**.

<img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/enable_json_09.png" width="400">

Select **WEM Portal**.

<img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/enable_json_10.png" width="400">

Disable the WEM Portal connection.

<img src="https://raw.githubusercontent.com/JS-DE-Tech/hacs-weishaupt-lan/main/docs/images/enable_json_11.png" width="400">

> [!IMPORTANT]
> The local CanApiJson interface used by this integration only works when the WEM Portal connection is disabled.
>
> If WEM Portal is enabled, the Systemgerät reserves the communication channel for the cloud connection and Home Assistant will not be able to communicate with the controller.
>
> You must choose either:
>
> - **WEM Portal (Cloud Access)**, or
> - **Home Assistant via CanApiJson (Local Access)**
>
> Simultaneous operation is not supported by the Systemgerät firmware.

#### Verify Connectivity

After enabling the JSON interface and disabling WEM Portal, verify that:

- The Systemgerät is connected to the local network.
- Home Assistant can reach the Systemgerät IP address.
- TCP port 80 is reachable from the Home Assistant host.
- The configured IP address in the integration matches the Systemgerät.

Once these requirements are met, the integration can be added to Home Assistant.

## Installation

### HACS — Custom Repository

1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Open the menu in the upper-right corner.
4. Select **Custom repositories**.
5. Add this repository URL and select **Integration** as the category.
6. Install **Weishaupt WTC LAN**.
7. Restart Home Assistant.

The local `icon.png` is included for repository and HACS presentation. It does
not automatically create a native Home Assistant frontend brand icon for the
custom domain `weishaupt_wtc_lan`.

### Manual Installation

1. Copy the folder:

   ```text
   custom_components/weishaupt_wtc_lan
   ```

   to:

   ```text
   /config/custom_components/
   ```

2. Restart Home Assistant.

## Configuration

1. Go to **Settings** → **Devices & Services**.
2. Select **Add Integration**.
3. Search for **Weishaupt WTC LAN**.
4. Enter the IP address or hostname of the Systemgerät.
5. Optionally adjust the username, password, polling interval, and experimental diagnostics toggles.
6. Review the detected heating-circuit display names and edit them if needed.

The polling interval can be configured from **30 to 600 seconds** in steps of **10 seconds**.

Recommended polling intervals:

- Normal operation without experimental sensors: **30 seconds**
- Curated experimental sensors enabled: **60 seconds or slower**
- Extended experimental diagnostics enabled: **120 seconds or slower**

The same options can be changed later from the integration options. Saving the options reloads the integration so the new polling interval, display names, and diagnostic options take effect without removing the integration.

Heating-circuit names are display names only. Entity unique IDs, device identifiers, and CanApiJson register addresses remain stable when names are changed.

## Request Safety and Write Settling

All CanApiJson HTTP requests are serialized through one shared client lock. The
integration keeps a conservative minimum gap of **300 ms** between completed
requests and the next request start. Regular read batches remain capped at six
VG frames.

Writable select, number, and one-shot button entities are queued centrally in
the coordinator. Rapid changes are debounced for **750 ms**; repeated writes to
the same register keep only the newest pending value, while writes to different
registers are still sent one at a time in order.

After the final queued write is acknowledged, the integration waits for a
**10-second** quiet period and then requests one coordinator refresh. During
queued writes and the post-write settling window, ordinary full polling reads
are skipped and Home Assistant keeps showing the last-good coordinator data.
Acknowledged configured target values are reflected optimistically, but actual
state mirrors are not fabricated until a real device poll confirms them.

If a later dynamic read batch times out or returns no data, previously valid
dynamic values are preserved. This avoids unrelated entities becoming
unavailable because one batch failed temporarily.

## Optional Experimental WTC Diagnostics

The integration can optionally expose a separate read-only diagnostics device
containing selected unconfirmed WTC registers.

Enable this feature from the integration options:

```text
Enable experimental read-only WTC sensors
```

The experimental sensors are intended for real-hardware correlation testing.
They expose raw values, address metadata, confidence hints, and derived raw
attributes but do not provide write support.

The feature is disabled by default. When disabled, no experimental device,
entities, setup probes, or polling requests are added.

A second option is available for a broader explicitly curated catalog:

```text
Enable extended experimental read-only WTC sensors
```

This option is also disabled by default and is only evaluated when the curated
experimental option is enabled. The extended catalog is capped at 100 explicitly
listed entities and is currently empty because the committed discovery artifacts
are broad scan outputs, not a defensible curated address list.

For correlation work, call the Home Assistant service:

```text
weishaupt_wtc_lan.export_experimental_snapshot
```

It writes JSON and CSV files under:

```text
/config/weishaupt_wtc_lan_diagnostics/
```

The snapshot includes regular WTC values, network diagnostics when available,
curated experimental values, and extended experimental values when enabled. It
does not export passwords, authorization headers, tokens, cookies, or other
credentials.

## Device Detection and Naming

The integration organizes entities into separate logical Home Assistant devices.

When available, the local read-only inventory file:

```text
/sd/systable.csv
```

is used to detect installed modules and to derive default display names. Name
resolution is:

```text
explicit non-empty user override
-> detected systable.csv name
-> generic fallback
```

Detected heating-circuit names are stored separately from manual overrides as a
small parsed mapping, for example `{ "1": "Plattenwaermetauscher" }`. The raw
`systable.csv` file is not stored. Opening the integration options refreshes the
mapping when the file can be fetched; if the refresh fails, the last successful
detected names remain available.

The parser supports explicit HK markers, confirmed metadata fields that expose
`MI=0x02` with `MX=0x00`, `0x01`, or `0x02`, and the real local metadata format
confirmed on the validated installation:

```text
M02_*.BIN;<display name>;<circuit number>
```

Only `M02_*.BIN` rows are interpreted as heating-circuit display names, so a
warm-water row such as `M03_*.BIN;Warmwasserspeicher;1` is not treated as HK1.
The same inventory can also provide optional logical display names for the
Systemgeraet, Warmwasser, network device, and WTC boiler while keeping stable
device identifiers and entity unique IDs unchanged.

Observed example from a real installation:

| Logical device | Display name from the installation |
|---|---|
| HK1 | `Plattenwaermetauscher` |
| HK2 | `Fussbodenheizung` |
| HK3 | `Heizkoerper` |
| Domestic hot water | `Warmwasserspeicher` |
| Network | `GATEWAY0` |
| Boiler | `WE0` |

External heating circuits are only created when the corresponding CanApiJson module returns plausible responses.

Optional modules such as Solar are only created when inventory detection and setup-time probing indicate that the module is actually present. If a previously created optional module is no longer present, stale integration-owned devices can be cleaned up.

## Devices and Entities

### Systemgerät

The Systemgerät device contains system-wide values:

- system operating mode
- current system operating-mode display
- outdoor temperature
- heating demand
- domestic-hot-water demand
- plate heat exchanger temperature
- upper and lower buffer-storage temperatures
- selected cascade values
- CANopen error/warning diagnostic block
- combined date/time value
- separate diagnostic device date and clock-time values

`Datum Anlage` and `Uhrzeit Anlage` are derived from the existing raw
Systemgeraet date/time component registers and are enabled by default. The raw
component entities remain disabled by default. Validated date byte order is:

```text
01/00/2563/02 -> year offset
01/00/2563/03 -> month
01/00/2563/04 -> day
```

### HK1 — Integrated Heating Circuit

HK1 is exposed as its own logical Home Assistant device.

Stable technical addressing:

```text
MI = 0x02
MX = 0x00
```

Entities include:

- operating mode: configured and current
- summer/winter changeover
- current status
- room target temperatures: comfort, normal, reduced, current
- flow target temperatures: comfort, normal, reduced, special level, current
- current flow temperature

### HK2 and HK3 — External Heating Circuits

External EM-HK heating circuits are detected automatically and exposed as separate logical Home Assistant devices.

Technical addressing:

```text
HK2: MI = 0x02, MX = 0x01
HK3: MI = 0x02, MX = 0x02
```

HK2 intentionally retains the historic technical key prefix `hk_`, for example
`hk_betriebsart_vorgabe`, to preserve existing unique IDs, dashboards, and
automations. The display name still identifies the device as HK2.

Entities include:

- operating mode: configured and current
- summer/winter changeover
- current status
- room target temperatures: comfort, normal, reduced, current
- flow target temperatures: comfort, normal, reduced, special level, current
- current flow temperature

### Domestic Hot Water

Domestic hot water is exposed as a separate logical Home Assistant device.

Entities include:

- current status
- one-shot hot-water push button
- normal target-temperature slider: **50 to 60 °C** in **1 °C** steps
- reduced target-temperature slider: **8 to 60 °C** in **1 °C** steps
- current target temperature
- current hot-water temperature
- circulation return temperature
- hot-water pump status

A permanent domestic-hot-water enable/disable register has not yet been confirmed reliably through the local CanApiJson interface. Therefore, the integration currently does not expose a permanent hot-water on/off switch.

The existing hot-water push register is a one-shot action and must not be used as a permanent on/off switch.

### WTC Boiler

The WTC boiler device contains boiler-specific runtime values:

- WTC operating phase
- burner operating phase
- flow target temperature
- boiler temperature
- return temperature
- flue-gas temperature
- VPT volume flow
- system pressure
- VPT thermal output
- remaining time until maintenance
- maintenance interval
- burner starts total
- burner operating hours total
- previous-day heat quantity:
  - total
  - heating
  - domestic hot water

The flue-gas-temperature and return-temperature registers were empirically confirmed on real hardware.

`VPT thermal output` is probed adaptively during setup. The integration tries
the confirmed address with `VS=4` first and falls back to `VS=2` for devices
that return a shorter response. A raw value of `0` remains a valid `0.0 kW`
state.

The regular WTC boiler device also exposes the empirically confirmed
`Burner Starts Total` and `Burner Operating Hours Total` counters. Mirrored
counter addresses exist on tested hardware, but the integration uses only
`09/01/2920/00` and `09/01/2921/00` for these regular entities until the
resettable-vs-lifetime distinction is verified further.

The maintenance values are read-only diagnostics. They were empirically
confirmed on tested hardware but are not used for reset or write operations.

### Weishaupt Systemgeraet Netzwerk

When at least one network value responds, the integration creates a separate
read-only `Weishaupt Systemgeraet Netzwerk` device attached to the Systemgeraet
device. The stable device identifier remains `<entry_id>_network`.

Entities include:

- Gerätename, from the optional read-only `06/00/250E/00 VS=16 GETS` string
  read when supported
- Zertifikat-CN, from the optional read-only `06/00/2511/00 VS=50 GETS` string
  read when supported
- MAC-Adresse, derived from six read-only `06/00/250C/01..06 VS=2` components
- IP mode
- IP address
- subnet mask
- gateway
- DNS server

Network values are read immediately during integration setup or reload and are
kept as cached coordinator data. During normal operation they are synchronized
at most once every 10 minutes, outside the ordinary heating-system polling
batch. A temporary network diagnostic read failure keeps the last successful
value. Network diagnostic entities are enabled by default in the entity
registry. IP mode raw value `1` is confirmed as `Manuell`; raw value `3` is
confirmed as `Automatisch (DHCP)`.

The configured device name and certificate CN use optional string-read probes.
They are created only when the string read returns a non-empty value, and string
read failure never fails setup. `06/00/2505/00` is a web UI write address and is
not used by the integration. The MAC address is exposed only when all six
components are available; the six component registers are not visible entities.

No network write support is implemented. Credentials, passwords, usernames,
cookies, tokens, and HTTP authorization data are not exposed.

The Home Assistant network device exposes a native configuration link to
`http://<configured-host>/`. Opening that local Systemgeraet web page remains an
explicit user action and may show the browser's normal authentication prompt.

### Solar

The Solar device is only created when a corresponding module is detected and setup-time probing returns plausible values.

Entities include:

- collector temperature
- lower storage temperature
- solar yield:
  - total
  - today
  - previous day

If all known Solar registers are missing or return only sentinel values, the Solar device is not created.

## Writable Controls

### Heating-Circuit Operating Mode

Each detected heating circuit exposes a writable **Operating Mode Target** select with the following values:

- Standby
- Time Program 1
- Time Program 2
- Time Program 3
- Summer
- Comfort
- Normal
- Reduced

### System Operating Mode

The Systemgerät exposes a writable **System Operating Mode** select with the confirmed values:

- Standby
- Summer
- Automatic

The Systemgeraet also exposes `Systembetriebsart aktuell`, a read-only mirror
sensor derived from the same confirmed `sg_systembetriebsart` coordinator data.
It does not add another protocol read.

Redundant read-only HK2/HK3 operating-mode target sensors are removed on reload;
the writable HK1/HK2/HK3 selects and distinct actual-state sensors remain.

### Write Validation

Writes are accepted as successful only when the device returns a matching CanApiJson acknowledgement.

The integration rejects:

- error responses
- missing responses
- normal read responses instead of acknowledgements
- address mismatches
- value mismatches

Always verify write operations directly on the heating system after changing operating modes.

## Confirmed CanApiJson Runtime Registers

The following registers were confirmed through real read-only API responses on tested hardware.

| Value | MI | MX | OX | OS | VS | Scaling |
|---|---:|---:|---:|---:|---:|---|
| System operating mode | `0x01` | `0x00` | `0x261E` | `0x00` | `1` | enum |
| HK operating mode target | `0x02` | circuit index | `0x2533` | `0x02` | `1` | enum |
| Outdoor temperature | `0x01` | `0x00` | `0x26B1` | `0x02` | `2` | × 0.1 °C |
| Plate heat exchanger temperature | `0x01` | `0x00` | `0x261F` | `0x02` | `2` | × 0.1 °C |
| Boiler temperature | `0x07` | `0x00` | `0x2532` | `0x00` | `2` | × 0.1 °C |
| Flue-gas temperature | `0x07` | `0x00` | `0x2533` | `0x02` | `2` | × 0.1 °C |
| Return temperature | `0x07` | `0x00` | `0x2537` | `0x00` | `2` | × 0.1 °C |
| Flow target temperature | `0x07` | `0x00` | `0x2545` | `0x00` | `2` | × 0.1 °C |
| VPT volume flow | `0x09` | `0x01` | `0x2613` | `0x02` | `2` | l/h |
| System pressure | `0x09` | `0x01` | `0x2614` | `0x02` | `2` | × 0.01 bar |
| VPT thermal output | `0x09` | `0x01` | `0x2631` | `0x02` | device-dependent response size | × 0.01 kW |
| Previous-day heat quantity: heating | `0x09` | `0x01` | `0x2626` | `0x02` | `4` | × 0.01 kWh |
| Previous-day heat quantity: hot water | `0x09` | `0x01` | `0x2627` | `0x02` | `4` | × 0.01 kWh |
| Previous-day heat quantity: total | `0x09` | `0x01` | `0x2628` | `0x02` | `4` | × 0.01 kWh |
| Burner Starts Total | `0x09` | `0x01` | `0x2920` | `0x00` | `2` | count |
| Burner Operating Hours Total | `0x09` | `0x01` | `0x2921` | `0x00` | `2` | h |

## Local Metadata Export

For troubleshooting heating-circuit name detection, call:

```text
weishaupt_wtc_lan.export_local_metadata
```

The service is read-only with respect to the heating system. It fetches
`/sd/systable.csv` and writes timestamped files under:

```text
/config/weishaupt_wtc_lan_diagnostics/local_metadata/
```

The JSON summary contains parsed heating-circuit names, persisted detected
names, whether detected-name usage is enabled, and the resolved display names.
It does not export passwords, authorization headers, tokens, cookies, or HTTP
credentials.

## Protocol Reliability Notes

The integration uses the Weishaupt CanApiJson protocol, a CAN-bus-like protocol transported as JSON over HTTP POST requests to:

```text
/ajax/CanApiJson.json
```

Read requests are sent in batches of up to **six** CanApiJson frames.

Testing on real hardware showed that larger mixed batches may cause individual frames to return `CMD_ERROR`, even when the same registers can be read successfully in smaller batches.

Valid raw zero values are preserved as measurements. Only known sentinel values are treated as unavailable:

```text
0x8000
0xFFFF
0x80000000
0xFFFFFFFF
```

Examples of valid zero values:

```text
VPT volume flow = 0 l/h
VPT thermal output = 0 kW
```

## Read-only Discovery Tools

The repository includes bundled read-only PowerShell tools in:

```text
discoverytool/
```

These tools are intended for diagnostics, register verification, and structured protocol research. They do not change heating-system settings.

> [!IMPORTANT]
> On installations where the WEM cloud connection and the local JSON interface are mutually exclusive, disable the cloud connection and enable the local JSON interface before running the tools.

### WTC Snapshot and Focused Discovery Package

Use:

```text
discoverytool/weishaupt-wtc-readonly-package.zip
```

This package contains two separate read-only tools:

1. A quick WTC snapshot tool that reads:
   - confirmed Systemgerät, hydraulic, and WTC values
   - plausible WTC candidates derived from portal screenshots
   - all previously discovered native WTC response objects

2. A focused extended WTC discovery scan for:
   - burner starts
   - burner operating hours
   - pump data
   - ionization values
   - gas-valve values
   - fan speed and fan-control values
   - additional WTC and WE0 portal parameters

The focused scan uses:

```text
MI = 0x07, MX = 0x00
MI = 0x09, MX = 0x01
OX = 0x2400 to 0x2AFF
OS = 0x00 to 0x0F
VS = 1, 2, 4
```

### Broad Structured Discovery Package

Use:

```text
discoverytool/weishaupt_discovery_skript.zip
```

This package performs a broader structured read-only scan across confirmed installation modules. It exports CSV and JSONL result files for later analysis.

### Discovery Tool Documentation

Additional usage instructions are provided in:

```text
discoverytool/README.md
```

### Safety Properties

The bundled discovery tools:

- use only read-only CanApiJson GET requests
- send no SET commands
- use batches of up to six CanApiJson frames
- preserve valid raw zero values
- support checkpoint-based continuation for longer scans
- export results for offline analysis


## Experimental Register Research

Additional read-only WTC, heating-circuit, domestic-hot-water, and diagnostic parameters are currently being investigated.

Portal screenshots and structured local discovery scans indicate additional potentially useful values, including:

- burner starts
- burner operating hours
- pump modulation
- ionization signal values
- gas-valve values
- fan speed and fan-control values
- outdoor-temperature minimum and maximum
- heating-curve parameters
- heating-circuit optimization values
- domestic-hot-water loading strategy
- legionella-protection settings
- fault-memory values

Some of these values have already been discovered as raw CanApiJson objects but are not yet exposed as Home Assistant entities because their exact meaning, scaling, or behavior has not been confirmed sufficiently on real hardware.

## Protocol Research

This implementation is based on the research and documentation published in:

[BorgNumberOne/Weishaupt_CanApiJson](https://github.com/BorgNumberOne/Weishaupt_CanApiJson)

## Project History

This repository is based on the original:

[kraiz/hassio-weishaupt](https://github.com/kraiz/hassio-weishaupt)

created by Lars Kreisz.

This fork is maintained and extended by Jens Saffrich (JS TechSector).

Major enhancements include:

- support for multiple heating circuits
- separate logical Home Assistant devices
- domestic-hot-water temperature controls
- writable heating-circuit operating-mode selects
- writable system operating-mode select
- automatic module detection
- heating-circuit naming from the local inventory
- improved optional-module detection and stale-device cleanup
- additional empirically confirmed WTC boiler parameters
- bundled read-only PowerShell snapshot and discovery packages
- stricter handling of CanApiJson responses
- correct handling of sentinel values and valid zero values
- configurable polling interval
- improved Home Assistant entity and device organization

## License

MIT
