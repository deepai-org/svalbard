# Held CML-to-CMOS retimer

This directory is a routed GF180MCU development checkpoint for the CDR's
CML-to-CMOS boundary.  It is **not an analog signoff claim**.  The present
active-high NOR-latch candidate is schematic-functional and physically clean,
but the full-RC extracted circuit does not yet meet the 800 ps throughput
contract.

![Current routed layout](layout.png)

## Current evidence

- Schematic nominal matrix: 9/9 pass at 100, 200, and 400 mV differential
  input and 10, 25, and 50 fF differential output loading.
- Magic DRC: zero errors.
- Netgen LVS: circuits match uniquely.
- Full-RC PEX: 1,676 resistors and 1,204 capacitors.
- Extracted nominal matrix: 0/9 pass.  The output decision is approximately
  one 800 ps interval late on alternating data, so this is a real throughput
  blocker rather than a waived measurement.
- Extracted average supply current: 7.36 to 8.22 mA, below the 20 mA ceiling.

The committed JSON files are the exact nominal results behind this status.
`schematic_nominal_result.json` is passing;
`extracted_nominal_result.json` is intentionally failing and prevents this
cell from being promoted as complete.

## Architecture

The clocked differential pair precharges `XP`/`XN` high, regenerates the CML
decision during evaluation, and drives small isolation inverters.  Their
active-high outputs update a cross-coupled NOR latch; both return low during
precharge, so the latch holds.  Tapered CMOS buffers drive `OUTP`/`OUTN`.

The layout generator uses symmetric unit fingers, explicit body ties, a
contacted substrate guard ring, matched high-metal buses, and staggered latch
rows to prevent same-row local-route shorts.  The tail is directly adjacent to
the input pair and the sense-to-latch routes have been compacted relative to
the first routed candidate.

## Reproducing the checks

Use the repository's pinned `iic-osic-tools` ARM64 image and GF180MCU-D PDK.
The core commands are:

```sh
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" layout.tcl
sak-drc.sh -m -w /work/drc /work/cml_to_cmos.mag
sak-lvs.sh -m -w /work/lvs -s /src/cml_to_cmos.spice \
  -l /work/cml_to_cmos.mag -c cml_to_cmos
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_to_cmos_pex \
  -w /work/pex /work/cml_to_cmos.mag
python3 run_nominal.py --source /src \
  --pex /work/pex/cml_to_cmos.pex.spice --work /work/extracted \
  --output /work/extracted.json --eval-width-ps 500 --timeout-s 300
```

Next work is to reduce the extracted sensor-to-held-output delay, then rerun
the full normalized PVT matrix.  No PVT or Monte Carlo result should be read
into the current checkpoint until nominal full-RC throughput passes.

