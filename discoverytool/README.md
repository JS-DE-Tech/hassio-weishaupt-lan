# Weishaupt Discovery Tools

This directory contains read-only discovery and correlation tools for the local Weishaupt CanApiJson interface.

## Safety

All included scripts operate in read-only mode.

Only the following command type is used:

* `CM=0x01` (`GET`)

The tools never send:

* `CM=0x03` (`SET`)
* `CM=0x13` (`SETS`)

No configuration values are modified.

The tools communicate only with the local Weishaupt Systemgerät through the local CanApiJson HTTP interface.

---

## Requirements

Before running any tool:

1. Disable the WEM Portal cloud connection.
2. Enable the local JSON interface on the Weishaupt Systemgerät.
3. Extract the required ZIP package.
4. Run the supplied CMD launcher.
5. Enter the local Systemgerät password when prompted.

Do not run the local JSON interface and the WEM Portal cloud connection at the same time.

---

## Tool 1 – Snapshot Package

**File:**

`weishaupt-wtc-readonly-package.zip`

### Purpose

* Collect confirmed WTC boiler values
* Collect system and hydraulic parameters
* Collect known native WTC objects
* Collect heating-circuit and hot-water values
* Match local values against portal screenshots
* Create a compact baseline snapshot of the installation

### Output

`weishaupt-wtc-snapshot.zip`

### Recommended usage

Run this package first when analyzing a new installation or validating known registers.

### Typical runtime

`1–5 minutes`

---

## Tool 2 – Broad Discovery Scanner

**File:**

`weishaupt_discovery_skript.zip`

### Purpose

* Search broadly for undocumented readable registers
* Discover additional burner parameters
* Discover operating hours
* Discover pump information
* Discover fan information
* Discover ionization values
* Discover gas-valve parameters
* Discover additional portal-related values
* Create a reusable register inventory for later analysis

### Features

* Strictly read-only operation
* Automatic checkpoints
* Resume after interruption
* Metadata collection
* CSV and JSON export
* Persistent scan progress

### Output

`weishaupt-discovery.zip`

### Recommended usage

Run this scanner only when the Snapshot Package does not provide enough information or when investigating previously unknown register areas.

### Typical runtime

`25–45 minutes`

The runtime depends on the selected scan range and the response speed of the Systemgerät.

---

## Tool 3 – Targeted Correlation Scanner

**File:**

`weishaupt-targeted-correlation.zip`

### Purpose

The Targeted Correlation Scanner performs focused read-only scans of dynamic module areas that were identified from the real `systable.csv` topology and previous discovery scans.

It is intended for comparing register values under different operating conditions.

### Investigated module areas

```text
09/00 → Systemgerät or HK1-related dynamic values
09/01 → WTC boiler-related dynamic values
09/02 → HK2-related dynamic values
09/03 → HK3-related dynamic values
```

### Existing confirmed or curated reference candidates

```text
09/01/2610/02
09/01/2611/02
09/01/2612/02
09/01/2615/02
09/01/2619/02
09/01/263A/02
09/01/2679/00
09/01/268A/00
09/01/268B/00
09/01/268C/00
09/01/268D/00
09/01/268E/00
09/01/268F/00
09/01/2902/00
09/01/2903/00
09/01/2904/00
09/01/2905/00
09/01/2908/00
09/01/2922/00
```

### Included files

```text
START-targeted-correlation.cmd
weishaupt-targeted-correlation.ps1
README.txt
```

### Profiles

#### Quick

Reads the existing curated addresses across:

```text
09/00
09/01
09/02
09/03
```

Use this profile for quick comparisons between two operating states.

#### Focused

Reads the curated addresses plus selected adjacent object ranges:

```text
2610–261F
2630–263F
2670–267F
2680–268F
2900–290F
2920–292F
```

Each range is queried with selected subindices and supported numeric value sizes.

Use this profile for the initial targeted analysis or when searching for additional dynamic values near already known candidates.

### Features

* Strictly read-only `CM=0x01` queries
* Maximum of six frames per CanApiJson request
* Dense batch numbering without gaps
* Address-based response mapping
* Preservation of valid raw value `0`
* Sentinel-value detection
* Automatic checkpoint after each batch
* Resume after accidental interruption
* CSV and JSONL export
* Automatic comparison with the previous completed run
* Separate export for raw values `0` and `1`
* Visible output directory on the Windows desktop
* No password storage in result files

### Output folder

The script creates a visible folder on the Windows desktop:

`Desktop\Weishaupt_Targeted_Correlation`

Each scan creates a timestamped subdirectory:

`YYYYMMDD-HHMMSS-<label>-<profile>`

Example:

`20260611-221500-heizbetrieb_aktiv-Focused`

### Generated files

```text
results.csv
results.jsonl
supported-values.csv
unsupported-or-errors.csv
state-like-raw-0-or-1.csv
summary.json
run-metadata.json
probe-plan.json
```

When a previous completed run exists, the scanner also creates:

```text
changed-values-vs-previous-run.csv
comparison-source.txt
```

### Recommended correlation snapshots

Run the scanner several times with clearly named labels while deliberately changing only one operating condition at the heating system.

Recommended labels:

```text
brenner_aus
heizbetrieb_aktiv
warmwasserladung_aktiv
pumpennachlauf
hk2_pumpe_ein
hk2_pumpe_aus
hk3_pumpe_ein
hk3_pumpe_aus
```

### Recommended usage

For the first targeted scan:

1. Extract `weishaupt-targeted-correlation.zip`.
2. Double-click `START-targeted-correlation.cmd`.
3. Select `2 = Focused`.
4. Enter a descriptive label, for example `brenner_aus`.
5. Enter the local Systemgerät password when prompted.
6. Wait until the result folder opens automatically.
7. Compress the complete timestamped output folder as a ZIP file.
8. Upload the ZIP file for correlation analysis.

For later state comparisons, the faster `Quick` profile is usually sufficient.

### Typical runtime

```text
Quick profile:   approximately 1–5 minutes
Focused profile: approximately 10–30 minutes
```

The actual runtime depends on the number of supported registers, the response speed of the controller, and local network latency.

---

## Recommended Workflow

### Initial analysis of a new installation

1. Run the Snapshot Package.
2. Upload the generated snapshot ZIP file.
3. Review the confirmed and missing values.
4. Run the Broad Discovery Scanner only when additional undocumented registers are required.
5. Upload the generated discovery ZIP file.

### Targeted correlation of dynamic values

1. Run the Targeted Correlation Scanner with the `Focused` profile in a known baseline state.
2. Change exactly one operating condition at the heating system.
3. Run a second scan with a clear label.
4. Compare `changed-values-vs-previous-run.csv`.
5. Repeat the process for additional operating conditions.
6. Promote a register to the confirmed list only after its behavior has been verified reliably.

---

## Important Notes

* A raw value of `0` is a valid measurement and must not be treated as missing.
* Raw values `0` and `1` are not automatically binary values.
* Unknown registers remain experimental until their meaning has been confirmed through repeated correlation.
* Do not expose passwords, HTTP authorization headers, cookies, or tokens in logs or exported files.
* Upload complete result folders as ZIP files so that metadata, summaries, raw responses, and comparison files remain available for analysis.
