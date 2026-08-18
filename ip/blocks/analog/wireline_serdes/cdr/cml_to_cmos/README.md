# Held CML-to-CMOS retimer

This directory is a routed GF180MCU development checkpoint for the CDR's
CML-to-CMOS boundary. It is **not an analog signoff claim**. The reset-isolated
two-stage retimer meets its 800 ps schematic contracts and its nominal
200 mV extracted contract. A bounded extracted PVT smoke still identifies
reset/regeneration timing at extreme environments as the physical blocker.

![Current routed layout](layout.png)

## Current evidence

- Schematic nominal matrix: 9/9 pass at 100, 200, and 400 mV differential
  input and 10, 25, and 50 fF output loading.
- Schematic PVT smoke: 18/18 complete and all 9 representative environments
  pass at 100 mV stress and 200 mV contract sensitivity with 50 fF loading.
- Magic DRC: zero errors.
- Netgen LVS: circuits match uniquely.
- Full-RC PEX: 1,857 distributed resistors and 1,267 capacitors.
- Extracted nominal matrix: 6/9 pass. All six 200 and 400 mV contract cases
  pass; the three exploratory 100 mV cases fail. Minimum qualified contract
  logic margin is 232.2 mV at 200 mV input and 50 fF loading.
- Extracted average supply current: 9.01 to 9.53 mA, below the 20 mA ceiling.
- Extracted PVT smoke: 18/18 simulations complete across nine representative
  environments at 50 fF. Five of nine 200 mV contract cases and three of nine
  100 mV stress cases pass. Contract failures are fast/hot/high-common-mode,
  slow/hot/low-voltage at both common-mode limits, and
  slow/cold/high-common-mode. Their rail-level failures are not marginal and
  are not waived.

The committed JSON files are the exact results behind this status.
`extracted_nominal_result.json` fails because the 100 mV exploratory points
remain in that matrix, despite all 200/400 mV contract points passing.
`extracted_pvt_smoke_result.json` intentionally fails and prevents this cell
from being promoted as PVT-complete.

## Architecture

The clocked differential pair first acquires the CML input on small `SA`/`SB`
nodes. Those nodes gate a separate, stronger second-stage pair, isolating input
acquisition from the reset and positive-feedback capacitance on `XP`/`XN`.
Independent sense, regeneration, and capture phases prevent the previous
decision from fighting reset. Restoring inverters drive two matched
transmission-gate static latches; balanced CMOS inverters drive `OUTP`/`OUTN`.

The layout generator uses legal 0.8 um-pitch shared-diffusion fingers, explicit
body ties, a contacted substrate guard ring, matched high-metal buses, and
net-aware escape-column reuse that keeps low-metal terminal straps local. The
tail is directly adjacent to the input pair, the acquisition loads occupy the
open header row, and the matched output NFETs sit on a separate row to avoid a
same-height Metal2 conflict. This generated 190 by 160 um layout is the exact
geometry used for the committed image and extracted evidence.

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
  --output /work/extracted.json --eval-width-ps 575 \
  --regen-delay-ps 10 --capture-delay-ps 200 \
  --capture-width-ps 320 --timeout-s 300
```

`run_pvt.py --waveform-dir <path>` records the internal acquisition,
regeneration, restoration, latch, clock, and output nodes for selected cases.
Those waveforms show the physical trade directly: a 650 ps evaluation window
regenerates well but leaves only about 80 ps to reset routed `XP`/`XN`; the
575 ps selection restores nominal transition behavior but is too short at
several slow/extreme environments.

Next work is to strengthen and localize reset without materially increasing
`XP`/`XN` capacitance, then re-balance regeneration/capture timing. Only after
the representative extracted smoke passes should the full 729-case extracted
matrix, mismatch/noise, EM/IR, thermal/substrate, and top-level integration
work begin. The present smoke failures are not waived.
