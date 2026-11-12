# Superseded evidence (PD48, 2026-11-12)
The cell here is the PD48 1 kV build (no d2 row). These files describe the pre-PD48 2 kV d2 cell and are kept for history only:
`pd21-hspad-ac.json`, `pd21-hspad-power.json`, `pd21-hspad-rterm.json`, `pd21-hspad-rxpath.json`, `pd21-hspad-safe-hbm.json`,
`pd21-rl-cob-and-board-compensation.json` (RL ladder: use the die-C 1.0 pF case, board B40).
Current evidence: `../pd48-esd-tiering.json` (1 kV HBM, AC/RL), `lu.json` (PD48 LU audit), `pad_hspad-kldrc.json`.
Not rerun on the PD48 cell: rterm, rxpath, power-up (devices other than the d2 row are identical; review 1.7 notes macro routing not diffed).
