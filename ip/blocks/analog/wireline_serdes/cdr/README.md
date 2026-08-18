# Experimental GF180 dual-edge CDR sampler

This directory begins the `cdr` macro with the reference-assisted sampling front end required before autonomous clock recovery. Two complementary current-steering CML latches share `DATA_P/N`, a 1.25 GHz differential clock, and programmable tail bias. The even latch holds after `CLK_P` falls; the odd latch uses the swapped clock and holds after `CLK_P` rises. Together they expose raw even/odd decisions for a 2.5 GT/s stream.

Each latch steers one tail current between a differential tracking pair and a cross-coupled regenerative pair. The clock pair performs the steering below those devices, avoiding a separate large clock transistor in every signal source. Matched p-poly loads provide static CML outputs. This is a real transistor-level sampler, not the eventual Alexander decision logic or loop filter.

The schematic matrix completes 1,701/1,701 simulations over 3 MOS corners, 3
unsalicided-resistor corners, 3 supplies, 3 temperatures, 3 shared data/clock
common-mode fractions, and 7 bias settings. All 243 groups calibrate with an
interior 0.90--1.30 V setting while retaining the 0.80 and 1.40 V endpoints as
range margin.

The routed physical checkpoint is available below. It places the even
and odd latches as mirrored halves, keeps the regenerative devices and p-poly
loads local to their outputs, locates clock steering directly below each latch,
uses compact local tail connections, and surrounds the 96 x 55 um cell with a
contacted substrate guard ring. The full-resolution PNG is intended for quick
review; `layout.tcl` remains the editable, reproducible source.

![GF180 dual-edge CDR sampler routed layout checkpoint](layout.png)

The generated cell is now Magic DRC-clean and matches the schematic uniquely in
Netgen LVS. Its coupled full-RC extraction contains 480 resistors and 193
capacitors. A nominal extracted bias sweep passes four adjacent codes from
0.90--1.20 V with 0.233--0.701 V minimum signed decision margin.

Run the bounded reproducible evidence flow with:

```sh
make cdr-sampler-smoke
```

The full-RC PVT matrix also completes 1,701/1,701 simulations and calibrates
243/243 groups. Selected decision margin is 0.283--1.132 V, selected supply
current is 1.31--4.43 mA, and every group retains 3--7 passing codes. A further
720 extracted stress simulations pass 9/9 representative environments with one
fixed bias per environment over 10--50 fF load, at least 200 mV differential
data, at least 600 mV differential clock, and +/-50 ps clock displacement. The
270 deliberately out-of-envelope low-amplitude, 100 fF, offset, and combined
cases remain reported separately; 65 pass.

The 225-case aperture grid passes all nine environments over a qualified -80 to
+80 ps data-transition shift. Their common observed passing interval is -240 to
+80 ps; the negative boundary is censored because every environment still
passes at the -240 ps sweep limit. Another 225 extracted supply-injection cases
pass 9/9 environments for up to 50 mV-peak ripple from 10 MHz through 1.25 GHz
at two phases. All 72 separately reported 100 mV-peak cases also pass.

The programmable bias exists to absorb unknown global silicon, temperature,
supply, passive, and extracted-interconnect shifts while preserving margin away
from trim rails. It does not discover its own code: integration still requires
a reference-assisted calibration search and retained setting.

This remains a pre-signoff physical checkpoint. Statistical mismatch using a
provider-qualified model, metastability-tail statistics, autonomous phase
detection and loop dynamics, post-fill extraction, EM/IR, independent-simulator
correlation, and pad/package/board/channel co-simulation remain open. Results
are experimental pre-silicon public-model evidence, not PCIe compliance or
silicon qualification.

The transistor-level [half-rate Alexander phase-detector boundary](phase_detector/README.md)
is also DRC-clean, uniquely LVS-matched, and closed across full-RC PVT and
fixed-code stress. The next integration checkpoint combines two samplers and
two detector boundaries in the
[integrated half-rate detector](integrated_detector/README.md). Its coordinated
sampler-bias and edge-phase calibration closes across representative schematic
PVT; valid-window retiming, loop filtering, and autonomous closed-loop recovery
remain in progress.

The subsequent [dual-interleave phase-error combiner](phase_error_filter/README.md)
is now DRC-clean, uniquely LVS-matched, and full-RC closed across nine
representative environments. It sums both detector lanes into a signed
proportional error voltage while rejecting neutral and opposed votes. Vote
retiming, integration/control encoding, and autonomous loop closure remain the
next boundary.

The [aperture-qualified CML-to-CMOS front end](cml_to_cmos/README.md) now has a
zero-DRC, uniquely LVS-matched layout and closes all nine nominal full-RC
input/load cases at 800 ps throughput. Its programmable two-mode tail closes
all nine representative extracted PVT contract environments at 200 mV input;
seven of nine paired 100 mV stress cases also pass. The measured late-valid
interval is now composed with the routed clocked deserializer rather than
duplicating state retention inside the analog boundary. Both cells are full-RC
extracted, and the 18-case composition closes all nine representative
environments with a common 1000 ps capture close and measurement before the
following capture opening. Parallel RX integration and autonomous closed-loop
recovery are next.
