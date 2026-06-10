# Weishaupt WTC — Home Assistant Integration (no Cloud)

Custom Home Assistant integration for Weishaupt heating systems using the local **CanApiJson** protocol (JSON over HTTP).

The integration communicates directly with the **Weishaupt Systemgerät (SG)** on the local network. No cloud connection is required.

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
2. Enable the JSON interface in the Systemgerät settings.
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

> [!NOTE]
> The local JSON interface and the WEM cloud connection may be mutually exclusive on some installations. Disable the cloud connection before enabling and using the local JSON interface if required by your Systemgerät.

## Installation

### HACS — Custom Repository

1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Open the menu in the upper-right corner.
4. Select **Custom repositories**.
5. Add this repository URL and select **Integration** as the category.
6. Install **Weishaupt WTC**.
7. Restart Home Assistant.

### Manual Installation

1. Copy the folder:

   ```text
   custom_components/weishaupt_wtc
   ```

   to:

   ```text
   /config/custom_components/
   ```

2. Restart Home Assistant.

## Configuration

1. Go to **Settings** → **Devices & Services**.
2. Select **Add Integration**.
3. Search for **Weishaupt WTC**.
4. Enter the IP address or hostname of the Systemgerät.
5. Optionally adjust the username, password, polling interval, and heating-circuit display names.

The polling interval can be configured from **10 to 600 seconds** in steps of **10 seconds**.

The same options can be changed later from the integration options. Saving the options reloads the integration so the new polling interval and display names take effect without removing the integration.

Heating-circuit names are display names only. Entity unique IDs, device identifiers, and CanApiJson register addresses remain stable when names are changed.

## Device Detection and Naming

The integration organizes entities into separate logical Home Assistant devices.

When available, the local read-only inventory file:

```text
/sd/systable.csv
```

is used to detect installed modules and to derive default display names.

Observed example from a real installation:

| Logical device | Display name from the installation |
|---|---|
| HK1 | `Plattenwaermetauscher` |
| HK2 | `Fussbodenheizung` |
| HK3 | `Heizkoerper` |
| Domestic hot water | `Warmwasserspeicher` |
| Boiler | `WE0` |

External heating circuits are only created when the corresponding CanApiJson module returns plausible responses.

Optional modules such as Solar are only created when inventory detection and setup-time probing indicate that the module is actually present. If a previously created optional module is no longer present, stale integration-owned devices can be cleaned up.

## Devices and Entities

### Systemgerät

The Systemgerät device contains system-wide values:

- system operating mode
- outdoor temperature
- heating demand
- domestic-hot-water demand
- plate heat exchanger temperature
- upper and lower buffer-storage temperatures
- selected cascade values
- CANopen error/warning diagnostic block
- date and time values

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
- previous-day heat quantity:
  - total
  - heating
  - domestic hot water

The flue-gas-temperature and return-temperature registers were empirically confirmed on real hardware.

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
