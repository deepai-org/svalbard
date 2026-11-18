# Independent review 5: pt_lna round 2 (2026-11-18/19)

Artefacts, not conclusions. Repo /home/ubuntu/svalbard, project projects/programmable_transceiver_platform, block analog/rf_rx.
Rules: scratch/reviews/MANDATE.md (sections 2-4, 6, 8). Previous review brief: scratch/review-lna4/BRIEF.md (same artefact list);
its findings are summarised in scratch/rf-lna-q/NOTES.md. Coordinator decisions for this round are quoted in NOTES.md / the
interface rows RQ-1..RQ-5 at the end of scratch/reviews/interface-changes.md (site option B is the bond map; the 1.0 ohm
resistance rows above 9 GHz stay recorded as misses and are NOT to be re-litigated).

Changed since review 4 (verify each against the files; `git log -6 -- projects/programmable_transceiver_platform/analog/rf_rx`
and the working tree): gate-bias filter (60 kohm + NMOS gate capacitor on vg), common-mode network 0.27 pF / 95 ohm, degeneration
spirals halved (lna_spiral.G_DEG), secondary ESD clamps (off PMOS to VDD + off NMOS to VSS at g_p/g_n/bpc_p/bpc_n), vtk capacitor
on nfet_06v0, bench fix in tb._ladder_net (node names bwq*), new stages in lna_close.py (stab_b, startup, bounce, chain_point),
stage outputs in scratch/rf_rx/close/*.json, generated/lna-evidence.json, layout records generated/lna-layout.json / -lvs.txt.

Check, with your own runs where it matters (AC / noise / op only, at most 2 at a time, OMP_NUM_THREADS=1, 20-40 runs, no
transients, no layout; work only in scratch/review-lna5/; no project edits, no commits, no report files - reply in text):
1. Do the two "real" stability fails of review 4 hold as fixed? (a) supply anti-resonance 45-100 MHz: with the pads owner's
   coupled model (lna_match.stability(pkg='B_min'|'B_nom'|'B_max', cdie=, rdie=, rsw=, f1=5e6, f2=1e9, ppd=400)) and - separately -
   with the lossless lumped rails (lsup=1e-9 / 2e-9); (b) duplex bias (tb.set_lobias(True)) in band with the real supply network.
   Try a case of your own the owner did not run (e.g. island decap on top, B_max with lower wire resistance, se mode, sf/fs).
2. Are the off-MOS ESD clamps electrically what the owner says (junction diodes in the extracted netlist: ad/pd present? do they
   leak or load the gate at 3.63 V / 85 C; any DC path that shifts the gate bias; capacitance added)? Is the 6 V capacitor
   connected with the right polarity and bulk?
3. Is anything in generated/lna-evidence.json or analog/rf_rx/README.md section 5a / 6 stated as pass that its own numbers
   contradict, or stale against the files on disk (hashes)? Is the start-up criterion change (lna_close.startup docstring)
   legitimate or a limit moved after the result?
4. Chain NF rows (scratch/rf_rx/close/chain.json): is the DSB arithmetic from f_parts right, and is the owner's TIA x2 / x3
   estimate (OTA terms scale with en^2: 2.41 -> 1.75 / 1.44 nV/rtHz; +16.7k / +36.0k um2 per mixer) correct?
Reply <= 450 words: verdict (GO / GO with conditions / NO-GO for publication), ranked findings with numbers, reproduced vs read.
