# Weishaupt metadata dump

`dump_weishaupt_metadata.py` is a read-only diagnostic helper for checking
whether the local Weishaupt web interface documents additional hot-water mode,
hot-water enable/disable, or maintenance registers.

It only downloads:

- `/script/einstellung.js`
- `/script/Form_eth_log.js`
- `/sd/systable.csv`

It does not send CanApiJson `SET` commands and does not print credentials.

Example:

```powershell
$env:WEISHAUPT_PASSWORD = "Admin123"
python tools/dump_weishaupt_metadata.py --host 192.168.1.50 --output-dir weishaupt_metadata
```

After running it, inspect the files in `weishaupt_metadata/` for confirmed
register addresses before adding any new write entity.

## Confirmed register probe

`probe_weishaupt_registers.py` is a read-only helper for checking the currently
confirmed HK, system and WTC runtime registers against a real device. It only
sends CanApiJson `GET` frames to `/ajax/CanApiJson.json`, splits requests into
batches of up to six frames, never sends `SET` commands and never prints
credentials.

Example:

```powershell
$env:WEISHAUPT_PASSWORD = "Admin123"
python tools/probe_weishaupt_registers.py --host 192.168.1.50
```

The output includes the request VG, response VG, raw value in hex and decimal,
and the decoded value where a scale or value map is known. Register 167
(`wtc_abgastemperatur`) and register 168 (`wtc_ruecklauftemperatur`) are
empirically confirmed.
