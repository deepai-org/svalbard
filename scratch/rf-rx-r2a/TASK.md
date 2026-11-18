# Task A (RF RX owner's helper): make run_rf_rx.sh safe again and regenerate the stale RX evidence

Repo /home/ubuntu/svalbard, project projects/programmable_transceiver_platform, directory analog/rf_rx (owner's notes:
scratch/rf-lna-q/NOTES.md; README.md of analog/rf_rx sections 2, 5a, 6; binding rules scratch/reviews/MANDATE.md sections 4, 8).

State: the LNA was redesigned (new pins `tail`, `vtk`; real COB channel instead of the old board network). Its evidence is now
written by `analog/rf_rx/lna_close.py` -> `generated/lna-evidence.json`. `characterize.py` still contains the old LNA code path
(`do_lna`, BOARD_TRIM, the legacy bonded source return) and `summarize.py` renders section 5 of README.md from the evidence files.
`generated/rxmix_i-evidence.json`, `rxmix_q-evidence.json`, `bb_tap-evidence.json`, `rf_rx_chain.json`, `rf_rx-summary.json`,
`rf_rx_linearity.json` describe earlier cells (hashes do not match the files on disk).

Do:
1. `characterize.py`: make `--blocks lna` delegate to `lna_close.py` (or drop `do_lna` and have main() skip the LNA with a clear
   message), remove dead LNA-board code that cannot run on the new pin list, keep rxmix / bbfilter / bb_tap paths working. The
   chain rows that rxmix / bbfilter evidence use must come from the current cells: use `lna_close.chain_point` results
   (`scratch/rf_rx/close/chain.json`) or state "not available" - never a pinned number from an older LNA.
2. `summarize.py`: must not crash on the new `lna-evidence.json` format and must not print pass for a failed row; LNA rows may
   simply point to README section 5a.
3. `run_rf_rx.sh`: must NOT regenerate layouts of published blocks by default (bbfilter_i/q are published: regenerating changes
   GDS hashes). Make layout regeneration opt-in (flag) and evidence-only the default; document in the script header.
4. Regenerate `rxmix_i`, `rxmix_q`, `bb_tap` evidence from the cells on disk (`python3 characterize.py --blocks ... --jobs 1`),
   with fail states where rows fail; add sf / fs corners where the code sweeps corners (simlib.CORNERS is tt/ss/ff only; the
   sim header already supports 'sf' and 'fs'). Do not touch netlists.py, lna_layout.py, any .spice, any layout record or GDS.
5. Record what you changed and what still fails in your final reply (no report files; plain text reply, <= 500 words).

Machine rules: shared box. You may run AT MOST ONE simulation job at a time (`--jobs 1`), `OMP_NUM_THREADS=1`. DO NOT start any
simulation until the file /home/ubuntu/svalbard/scratch/rf-lna-q/GO exists (the owner's own runs hold the slots until then); do
the code reading and editing first, then wait for it with a loop like `until [ -f .../GO ]; do sleep 30; done` (commands longer
than ~3 min get backgrounded: poll). Do not commit, do not push, do not edit files outside analog/rf_rx except your scratch
directory /home/ubuntu/svalbard/scratch/rf-rx-r2a/. Do not edit lna_close.py, tb.py function signatures, or lna_match.py
(the owner is using them); if you need a change there, say so in the reply.
