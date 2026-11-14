# New core-support cells: claims and evidence — 2026-11-14 (PUBLISHED in distribution/generated/ after review)

Generator: `$P/analog/core_support/distribution/circuits_ext.py` + `generate_ext.py` (same row generator and unit devices as the
published bias banks; `circuits_dist.py` untouched). Staged outputs `bias/pub/` (mag, gds.gz, schematic `.spice`, C-only
extracted `.ext.spice`, lvs, layout json). Benches `bias/gen.py` (views sch / ext) -> `bias/run_<view>/`, `bias/collect.py`
-> `bias/results.txt`, `bias/results.json`. Checks: `bias/lay.out` (Magic DRC, netgen LVS, KLayout DRC with the PDK deck, HRES),
`bias/rb/` (read-back LVS with `scratch/integration/signoff-gap/lvs/rb_lvs.py`: GDS from disk -> Magic -> netgen + device
census; negative control `rb/neg_txpad_bias`), `bias/kl/` (precheck decks via `verification/kl_block_drc.py`, sha-matched).

| Cell | Purpose (demand) | Ports | Size (um) | Magic DRC | LVS (generator / GDS read-back) | KLayout PDK deck / precheck main / antenna | HRES |
|---|---|---|---|---|---|---|---|
| `pt_bias_tap2` | two more switched 10 uA outputs on an island trunk, no diode (D-BIAS, USB-D6) | VDD VSS TRK EN0 EN1 OUT0 OUT1 | 93.74 x 23.66 | 0 | unique / unique, census 10/10 | 0 / 0 / 0 | n/a |
| `pt_refvcm` | refpad VCM = VDD/2, gated (D-REFVCM) | VDD VSS EN VCM | 137.88 x 53.98 | 0 | unique / unique, 12/12 | 0 / 0 / 0 | 4/4 |
| `pt_txpad_bias` (x5 detect mirror, rebuilt after review) | TX termination buffer REF + BIAS dividers (gated), TX-pad detect PMOS bias (D-TXTERM) | VDD VSS EN BUF_REF BUF_BIAS EN_DET IBIAS_DET DETECT_PBIAS | 167.29 x 61.14 | 0 | unique / unique, 39/39 | 0 / 0 / 0 | 13/13 |

Read-back negative control: reference with one divider resistor disconnected -> "Top level cell failed pin matching" (mismatch).

## Extracted results (13 MOS corners: tt27, ss/ff x 22/32 at 3.15/3.35, sf/fs, safety ff 0/85 at 3.63, ss 0/85 at 3.15; + res_ss/res_ff crossed on 3 corners)

`pt_bias_tap2` (root + bank4 + tap on one trunk, ideal 10 uA reference, consumers = 4/2 um NMOS diodes):
- tap output 10.054-10.195 uA, tap/bank ratio 1.0000 at every corner; follows the reference 1:1 (8 uA -> 8.10, 12 uA -> 12.11).
- disabled output <= 6.5 pA; rail at 0 V with everything enabled: 0 output, 0 back-drive.
- output compliance: within 1.3 % from 0.2 to 2.0 V, -7.3 % at 2.8 V (ss).
- **rail offset between tap and bank: 3.4 % per 10 mV (tap/bank 0.900 at -30 mV, 1.105 at +30 mV). The tap must sit on the
  bank's own rail, abutting it.** Negative control: no reference -> 0 output.
- supply ripple -> output current (any bank or tap, tt): 0.3-2 uA/V at 100 kHz, 2.6-16 uA/V at 1 MHz, 10-26 uA/V at 78 MHz for
  0.3-3 pF of trunk capacitance (consumer diode node 63-156 mV/V at 78 MHz). A 5 pF trunk-to-rail capacitor brings 78 MHz to 8-11 uA/V.
  This is a property of the existing banks too (not new).

`pt_refvcm`: EN=1 VCM/VDD 0.4984-0.4992, 15.4-28.7 uA; EN=0 VCM <= 1 uV, <= 2.3 nA. Enable to 99 %: 3.1-4.1 us (pad bias strings
95 % in 2.2-2.8 us). |Z(VCM)| 27-35 kohm at 1 MHz, ~1 kohm at 50 MHz, 20-22 ohm at 2.4 GHz. Negative control: EN=0 judged as EN=1 fails.

`pt_txpad_bias`: EN=1 BUF_REF/VDD 0.4967-0.4984 (bench fixture 0.5; -5.5 mV worst), BUF_BIAS/VDD 0.2714-0.2721 (fixture 0.2727);
dividers ~195 uA. EN=0: both <= 0.5 uV, <= 5 nA. Enable to 99 % with the buffer's gate loads: REF 27-39 ns, BIAS 60-88 ns
(53-77 / 114-167 ns at 2x load). Detect bias with 10 uA into IBIAS_DET and EN_DET=1: each pad DETECT source (pfet 4/2) carries
99-101 uA at tt/ff/sf/fs, **90-93 uA at ss 22-32 C / 3.15 V, 82-83 uA at ss/85 C** (the x10 NMOS mirror runs out of headroom:
DETECT_PBIAS at 0.17-0.20 V); EN_DET=0: PBIAS = VDD, leak < 1 pA.

Not done: mismatch / Monte Carlo; R extraction (C-only, as the banks); the termination buffer and TX pad re-run with this cell in
place of the divider fixture; supply-trim point 3.5 V (ratiometric cells; 3.63 V safety corners are in).

## After the independent review (`../review-cs/REVIEW.md`)

- `pt_txpad_bias` detect mirror changed from x10 to x5 (review finding 2: x10 had no headroom, 73-101 uA and supply-set). Rebuilt
  (`bias/pub2/`, `bias/lay2.out`): DRC 0, LVS unique, read-back 39/39, precheck main 0 / antenna 0. Extracted, 19 corners:
  **49.5-50.8 uA per pad leg, DETECT_PBIAS >= 0.685 V**; REF / BIAS dividers unchanged. The x10 numbers above are superseded.
  The x5 rebuild itself was not re-reviewed (the reviewer's own x5 schematic variant gave 49.3-50.8 uA over nine corners).
- `pt_bias_tap2`: GO; condition = same rail as its bank, abutting (reviewer: bank rail off with the tap rail on gives 108-160 uA
  into the QVCO diode; +-50 mV of rail offset gives -16 % / +19 %). Into the real consumer diodes: 10.04-10.20 uA.
- `pt_refvcm`: GO; condition to state: it is a 40 kohm source, not stiff against DC-coupled pads. One pad pair held at 0 V pulls
  VCM to 0.90 V, at 3.3 V to 2.39 V; a single-ended 0/3.3 V clock shifts it by -0.37 V with +-123 mV of ripple at 10 MHz and the
  other pair follows; a complementary or AC-coupled drive causes no shift. HBM 2 kV on a refpad: VCM peaks at 1.5 V, no clamp needed.
- `pt_txpad_bias` dividers: GO; with the real gated buffer the output is 7-8 mV below the fixture case and settles within 2 % in
  1.4-2.0 ns when both are enabled together.
