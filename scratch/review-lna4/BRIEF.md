# Independent review 4: pt_lna (RF RX LNA redesign), 2026-11-18

You are an independent reviewer. You are given artefacts, not conclusions. Form your own verdict (GO / GO with conditions /
NO-GO for publishing `pt_lna` as the chip's on-chip LNA) and say plainly what you reproduced, what you only read, and what fails.

Repo `/home/ubuntu/svalbard`, project `projects/programmable_transceiver_platform`. Binding rules: `scratch/reviews/MANDATE.md`
(read sections 2, 3, 4, 6, 8 first). Previous review of the earlier cell: `scratch/review-lna3/REPORT.md`.

Artefacts under review (do NOT edit anything outside `scratch/review-lna4/`):
- `analog/rf_rx/netlists.py` function `lna()` and its constants; generated `analog/rf_rx/lna.spice`
- layout + records: `analog/rf_rx/generated/lna.{gds,ext.spice,lvs.spice}`, `lna-layout.json`, `lna-lvs.txt`, `lna-kldrc.json`;
  spiral cells `generated/lna_ind.gds`, `lna_deg.gds` and their models in `analog/rf_rx/lna_spiral.py`
- benches: `analog/rf_rx/tb.py`, `lna_match.py` (stability(), channel_ladder(), channel_fit()), `bench_selftest.py`,
  evidence script `lna_close.py` (limits are constants at its top) and its outputs `scratch/rf_rx/close/*.json`,
  `analog/rf_rx/generated/lna-evidence.json` (if present)
- owner's working notes and scratch scripts: `scratch/rf-lna-q/` (NOTES.md states the limits declared before the runs)
- context: `spec/performance-requirements.md` (RF-RX-NFSYS), `spec/package-channel.md`, `spec/power-delivery.md`,
  `spec/design-assumptions.md`, interface rows RQ-1..3 at the end of `scratch/reviews/interface-changes.md`

Questions to answer with your own checks (pick what matters most; you will not have time for everything):
1. Stability. Is the common-mode and differential stability bench physically meaningful and can it fail? Are there states,
   corners, terminations or supply networks it does not cover that could oscillate (think: bond inductances, mixers off,
   bypass, attenuator codes, duplex bias, sf/fs, power-up)? Try to break the design with a case of your own.
2. Circuit. Any error in the netlist: bias, headroom over corners and 3.15-3.63 V, off state / island-off safety, device
   stress, the tail and its mirror, the PMOS feed and MOS capacitor at 3.63 V, current density in the poly resistors
   (gate, degeneration damper, CM network), ESD exposure of the MIMs on the pad.
3. Benches. Is any limit bent, moved after a result, or reported as pass when its own numbers say fail? Is the real-channel
   model (bond, trace, connector, carrier parts) consistent with `spec/package-channel.md`? Is anything "ideal" where a real
   neighbour exists (pad model, mixer, LO, supply)?
4. Layout. Do the records match the files on disk (hashes)? Is the LVS meaningful (device parameters compared, negative
   control)? Anything in the extracted netlist (couplings, asymmetry P/N or I/Q) that the benches would not show?
5. Noise figure and gain. Are the reported numbers plausible, and is the stated reason for missing the 4.1 dB chain
   target (if it is missed) correct? What is the cheapest lever the owner has not used?

Machine rules: the box is shared. At most 2 simulations at a time (ngspice via the helpers in `analog/rf_rx/tb.py` /
`rfrx_flow.py`, which run a pinned docker image), always `OMP_NUM_THREADS=1`; AC / noise / op runs only (each 10-60 s);
no transient chain runs (30+ min each), no layout runs. Keep all your files in `scratch/review-lna4/`. Do not commit.
Write your report to `scratch/review-lna4/REPORT.md` (ranked findings with numbers, a reproduced / not reproduced list,
required actions before publication) and return a summary of at most 400 words.
