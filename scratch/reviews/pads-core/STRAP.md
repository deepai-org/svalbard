# POR_BYPASS strap pad (DT-10, D-POR): evidence

Cell: provider `gf180mcu_fd_io__in_c`, unmodified, bound exactly like `rst_n_pad`:
`PAD = POR_BYPASS`, `PD = VDD` (hard tie), `PU = VSS` (hard tie), `Y -> digital.por_bypass`.
No custom layout, no register, no island rail, nothing behind the POR. Transistor-level netlist from the PDK
(`scratch/transceiver-pad-pdk/gf180mcu_fd_io.spice`), GF180MCU-D ngspice models, pinned iic-osic-tools image.
Bench: `gen.py` (decks), `run.sh`, `collect.py` -> `results.json`. Reproduce: `../dock.sh 'bash /work/strap/run.sh'`.

## Result (all DC unless noted)

| Corner (MOS/T/VDD) | Input threshold (V) | Pull-down current at pad 0.4 / 0.8 V / VDD (uA) | Pad leakage with the pull-down OFF, pad at 0 V (nA, into pad) | Floating pad with pull-down (uV) | Up-current needed for pad = 0.4 V / to flip Y (uA) | Supply ramp 1 us / 100 us / 10 ms, pad floating + 2 pF: peak pad (V) |
|---|---|---|---|---|---|---|
| tt/27/3.3 | 1.09 | 3.06 / 6.11 / 25.2 | 0.038 | 4.9 | 3.06 / 8.38 | 0.345 / 0.181 / 0.128 |
| ff/85/3.63 | 1.05 | 3.82 / 7.63 / 34.5 | 0.105 | 10.9 | 3.82 / 10.1 | 0.311 / 0.107 / 0.028 |
| ff/85/3.63, res_ss | 1.05 | 2.57 / 5.14 / 23.3 | 0.105 | 16.2 | 2.57 / 6.88 | not run |
| ff/0/3.63 | 1.10 | 3.81 / 7.61 / 34.5 | 0.045 | 4.7 | 3.81 / 10.4 | 0.307 / 0.157 / 0.109 |
| ss/0/3.15 | 1.14 | 2.55 / 5.09 / 20.0 | 0.034 | 5.2 | 2.55 / 7.12 | 0.383 / 0.226 / 0.181 |
| ss/85/3.15 | 1.09 | 2.55 / 5.10 / 20.0 | 0.034 | 5.3 | 2.55 / 6.87 | 0.387 / 0.190 / 0.119 |
| sf/85/3.63 | 1.27 | 3.05 / 6.11 / 27.6 | 0.069 | 9.0 | 3.05 / 9.62 | 0.373 / 0.153 / 0.100 |
| fs/85/3.63 | 0.99 | 3.07 / 6.14 / 27.8 | 0.041 | 5.3 | 3.07 / 7.62 | 0.375 / 0.151 / 0.048 |
| ff/125/3.63 (exploratory) | 1.04 | 3.81 / 7.62 / 34.5 | 0.73 | 74.7 | 3.81 / 9.88 | 0.312 / 0.080 / 0.014 |

- The pull-down is a ~105-157 kohm path (resistor corner dominated). It holds the unbonded pad at 5-16 uV.
- Worst safety corner (ff / 85 C / 3.63 V): the cell's own leakage into the pad is 0.105 nA; it takes 2.57 uA
  (res_ss) to lift the pad to 0.4 V and 6.9 uA to flip `Y`. Margin 24,000x to 0.4 V, 65,000x to the flip.
  An external leak (flux, moisture, photocurrent) would have to exceed 2.5 uA, i.e. < 1.3 Mohm to 3.3 V.
- In every supply ramp `Y` stays at 0 (max of Y - VDD/2 is negative at all times); the pad's capacitive kick is
  <= 0.39 V against a threshold >= 0.99 V.
- Setting the strap: tie the pad to VDD. It draws 20-35 uA. Any source below ~10 kohm works (drop < 0.35 V).
- Negative control (pull-down disabled, PD = 0): the floating pad sits at 2.6-2.7 V with `Y` = 1 at tt and ss, and
  0.75 nA flips it at ff/85. So the bench does show a floating strap when there is one.

## ESD tier
Provider cell, unchanged, same as RESET_N and the host-link pads (2 kV HBM tier per MANDATE; the foundry cell's own
primary/secondary protection). `Y` is the cell's core-side buffer output: no core gate sits on the pad net, so the
PD28/PD29 core-gate screen has nothing to check. I did not simulate HBM on the provider cell (no pad owner has;
the project relies on the provider qualification for all provider pads).

## Not covered here
- The floating-strap case in the M6 chip power-up transient (M6 owner; DT-10 asks for it).
- `kl_assemble` / `kl_checks` tie check for the new pad (assembly; today only `rst_n_pad` is checked).
- If the strap goes on a non-provider site (extra pad opening), this evidence does not apply: see the option table.
