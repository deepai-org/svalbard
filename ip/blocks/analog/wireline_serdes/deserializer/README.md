# Differential half-rate capture stage

This directory begins the transistor-level `deserializer` child of the GF180
wireline SerDes. It captures the complementary CMOS decisions from the even
and odd CDR streams, retains both bits across the next acquisition, and exposes
complementary parallel outputs. This is a schematic and integration checkpoint,
not a routed macro or signoff claim.

Each lane uses two complementary, clock-gated NMOS write branches to force one
node of a cross-coupled static inverter latch. This direct differential write
path replaced a single-ended transmission-gate latch that entered metastability
at slow/hot corners. Tapered output buffers isolate retained state from four
external 50 fF loads. `CAPTURE_CLKB` is reserved at the top-level interface;
the current direct-write cell needs only the active-high capture phase.

## Executable evidence

The standalone schematic sweep runs 144 simulations across nine representative
MOS/supply/temperature environments, 680 and 700 ps input-ready times, 10 and
50 fF output loads, and 820, 850, 880, and 900 ps capture-closing phases. All
144 complete and all 36 environment/readiness/load timing groups pass. Every
tested closing phase passes every group. Minimum logic margin is 97.2 mV and
average current for both lanes is 3.59--5.92 mA.

The composition sweep replaces ideal inputs with the actual full-RC
CML-to-CMOS extraction (2,048 resistors and 1,340 capacitors), retains 50 fF on
both front-end rails and both captured outputs, and tests 36 cases across the
nine representative environments. All simulations complete and every
environment has a passing phase. The common passing closing range is 850--900
ps, minimum passing output margin is 120.3 mV, and combined one-lane front-end
plus capture current is 11.04--17.37 mA. The result is bound to both DUT hashes.

Run the schematic stage in the pinned GF180 container with:

```sh
python3 run_capture.py --source /src --work /work/capture \
  --output /work/capture.json --jobs 4
python3 run_integrated.py --source /src \
  --frontend-pex /front/cml_to_cmos.pex.spice \
  --work /work/integrated --output /work/integrated.json --jobs 4
```

## Remaining boundary

The phase is intentionally late relative to the nominal 800 ps decision-UI
label: the extracted front end holds the old decision while the following
acquisition begins. A 10 ps grid proves a common sampled-valid interval from
700 through 900 ps in the representative environments. This must still be
closed after deserializer layout, clock routing, and coupled extraction.

Next work is a symmetric two-lane generated layout, zero-DRC and unique-LVS
closure, full-RC re-simulation of the standalone and composed timing matrices,
then connection to the parallel digital receive path. Mismatch/metastability
tails, clock jitter and duty-cycle distortion, EM/IR, substrate/supply coupling,
post-fill extraction, and provider-qualified models remain outside this
checkpoint.
