# Held CML-to-CMOS retimer

This directory is a routed GF180MCU development checkpoint for the CDR's
CML-to-CMOS boundary. It is **not an analog signoff claim**. The current held
retimer meets its 800 ps nominal schematic and full-RC contracts, while a
bounded extracted PVT smoke identifies slow/hot reset recovery as the next
physical blocker.

![Current routed layout](layout.png)

## Current evidence

- Schematic nominal matrix: 9/9 pass at 100, 200, and 400 mV differential
  input and 10, 25, and 50 fF differential output loading.
- Magic DRC: zero errors.
- Netgen LVS: circuits match uniquely.
- Full-RC PEX: 689 resistors and 434 capacitors.
- Extracted nominal matrix: 9/9 pass. Minimum qualified logic margin is
  310.66 mV at 100 mV differential input and 50 fF output loading.
- Extracted average supply current: 5.09 to 5.83 mA, below the 20 mA ceiling.
- Extracted PVT smoke: 18/18 simulations complete across nine representative
  environments at 50 fF. Seven of nine 200 mV contract cases and five of nine
  100 mV stress cases pass. Both contract failures are slow-slow, 2.97 V,
  125 C reset-memory failures at the 0.60 and 0.80 VDD common-mode limits.

The committed JSON files are the exact results behind this status. Both
nominal summaries pass. `extracted_pvt_smoke_result.json` intentionally fails
and prevents this cell from being promoted as PVT-complete.

## Architecture

The clocked differential pair precharges `XP`/`XN` high and regenerates the CML
decision during evaluation. A falling sense node enables a PMOS set device on
a compact cross-coupled inverter latch. Both set devices turn off when the
sense nodes precharge, so the latch holds. Cross-connected, single-stage CMOS
inverters drive `OUTP`/`OUTN` with the required polarity.

The layout generator uses legal 0.8 um-pitch shared-diffusion fingers, explicit
body ties, a contacted substrate guard ring, matched high-metal buses, and a
compacted latch/output slice adjacent to the n-well boundary. The tail is
directly adjacent to the input pair. Moving the output devices and buses next
to the held latch was necessary to close nominal extraction.

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

Next work is a reset-isolated regeneration topology that erases the previous
decision at slow/hot corners without adding enough XP/XN capacitance to lose
nominal closure. After that change, rerun the full 729-case extracted PVT
matrix, bounded stress, and only then statistical and top-level integration
work. The present smoke failure is not waived.
