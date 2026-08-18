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
- Full-RC PEX: 1,465 distributed resistors and 967 capacitors.
- Extracted nominal matrix: 9/9 pass. Minimum qualified logic margin is
  41.44 mV at 100 mV differential input and 50 fF output loading.
- Extracted average supply current: 6.77 to 7.80 mA, below the 20 mA ceiling.
- Extracted PVT smoke: 18/18 simulations complete across nine representative
  environments at 50 fF. Six of nine 200 mV contract cases and three of nine
  100 mV stress cases pass. Two contract failures are slow-slow, 2.97 V,
  125 C reset-memory failures at the 0.60 and 0.80 VDD common-mode limits. A
  third slow-slow, 3.63 V, -40 C, 0.80 VDD common-mode case misses by 48.99 mV.

The committed JSON files are the exact results behind this status. Both
nominal summaries pass. `extracted_pvt_smoke_result.json` intentionally fails
and prevents this cell from being promoted as PVT-complete.

## Architecture

The clocked differential pair first acquires the CML input, then separately
phased NMOS and PMOS regeneration devices amplify the decision on `XP`/`XN`.
Small restoring inverters drive two matched transmission-gate static latches;
a late capture pulse updates them and their feedback paths hold between
decisions. Cross-connected, single-stage CMOS inverters drive `OUTP`/`OUTN`
with the required polarity.

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
  --output /work/extracted.json --eval-width-ps 575 \
  --regen-delay-ps 130 --capture-delay-ps 200 \
  --capture-width-ps 320 --timeout-s 300
```

`run_pvt.py --waveform-dir <path>` records the internal sense, regeneration,
restoration, latch, clock, and output nodes for selected cases. Extracted
waveforms show that slow/hot failures retain differential charge into the next
cycle. Directly enlarging precharge/equalization devices erases that memory but
adds enough `XP`/`XN` capacitance to lose evaluation closure, so those sizing
experiments were rejected.

Next work is a reset-isolated regeneration topology that erases the previous
decision without loading `XP`/`XN`. After that change, rerun the full 729-case
extracted PVT matrix, bounded stress, and only then statistical and top-level
integration work. The present smoke failures are not waived.
