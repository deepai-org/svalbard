# LNA ground and RF input on the standard 74-wire bond layout (pads owner, 2026-11-18)

PROPOSAL for the coordinator and the RF RX owner. `spec/contract.json` is not edited. Analytic filament model, not EM,
not measured. Tools and raw numbers: `scratch/pads-core/lnagnd/` (`bondl.py`, `mapopt.py`, `lnabench.py`,
`bondl.txt`, `mapopt.json`, `lnabench.json`). SPICE model for the LNA benches: `lna-bond-model.spice` (this folder).

## 1. What is fixed

- One wire per template pad, 74 wires, no extra openings, no down-bond, no double bond. 0.8 mil Al wire, die 250 um.
- West edge, north to south (bond): ... 63 GND, 64 PWR_AUX_1, 65/66 BB_Q_N/P, 67/68 BB_I_N/P, 69/70 RF_RX_N/P, 71 GND,
  72 VDD_CORE_1, 73 GND, 74 VDD_IO_3. Pitch 211 um on the die, 400 um at the fingers.
- Ground and supply sites cannot change function (their fingers are board ground / supply nets). A signal site made
  into a ground returns through 5.3-7.5 nH (trace, connector, carrier): no use at 2.4 GHz
  (`wafer-space-consequences.md` section 1).
- So there is no way to add ground wires. The LNA ground is die VSS, which reaches the board through the ten
  existing ground bonds; the two next to the LNA are 71 and 73.

## 2. Inductances (min / nom / max = short loop over run-2 ground copper / nominal loop over the In1 plane / high loop, no plane)

| Quantity | min | nom | max | nH |
|---|---|---|---|---|
| RF_RX_P wire (70), loop inductance | 1.83 | 2.24 | 2.86 | |
| RF_RX_N wire (69) | 1.79 | 2.18 | 2.78 | |
| Mutual P-N (coupling factor) | 0.31 (0.17) | 0.54 (0.24) | 1.06 (0.38) | |
| Differential inductance per leg (self - mutual) | 1.50 | 1.67 | 1.75 | |
| Ground bond 71 alone | 1.89 | 2.31 | 2.96 | |
| Bonds 71 and 73 in parallel (mutual 0.16 / 0.32 / 0.86) | 1.06 | 1.36 | 1.96 | |
| Bonds 63, 71, 73 in parallel | 0.66 | 0.83 | 1.22 | |
| All ten ground bonds (earlier figure, no mutuals) | | 0.23-0.26 | | |
| Common-mode loop: RX pair in parallel, return in 71 and 73 | 1.80 | 2.13 | 2.33 | |
| Mutual RF_RX_P / RF_RX_N to ground bond 71 | 0.33 / 0.14 | 0.57 / 0.28 | 1.12 / 0.76 | |
| Mutual RF_RX_P / RF_RX_N to VDD_CORE_1 bond 72 | 0.15 / 0.08 | 0.30 / 0.17 | 0.81 / 0.60 | |

Self-test of the tool (wire over a plane, Grover parallel filaments, split wire; wrong-sign image as the failing
control): pass. The nominal 2.24 nH agrees with the 2.33 nH of `bond-wire.json` (different formula, same geometry).

## 3. Effect on the LNA (generic pseudo-differential cascode CS stage, 450 um per leg, 0.47 nH on-chip degeneration; NOT the rf_rx netlist)

Limits declared before the runs are in the `lnabench.py` docstring. Known answer (bond network alone against a numpy
solve of the same matrix): -17.37 dB vs -17.37 dB (A), -38.83 vs -38.83 (B). Negative control (no coupling to the RX
wires, pads open): -240 dB.

| Quantity | Ideal ground | Today (RX on 69/70), min / nom / max | Proposed (RX on 67/68), min / nom / max | Limit |
|---|---|---|---|---|
| Differential gain at 2.42 GHz (dB) | 14.13 | 14.10 / 14.10 / 14.10 | 14.10 / 14.10 / 14.10 | change <= 0.5 dB: pass |
| Noise figure, spot (dB; PDK noise model, relative use only) | 1.565 | 1.590 / 1.590 / 1.591 | 1.590 / 1.590 / 1.590 | change <= 0.2 dB: pass |
| Common-mode Re(Zin) at the board side of the pair, minimum 0.1-30 GHz (ohm) | +0.63 (19 GHz) | -14.2 / -14.8 / -15.6 (about 0.4 GHz) | -16.0 / -17.5 / -18.7 | rf_rx's limit >= +1.0: FAILS in this generic stage |
| Die-VSS bounce to differential input, input-referred (dB) | none | -18.8 / -17.5 / -20.1 | -39.1 / -36.4 / -34.8 | B >= 6 dB better than A: pass (18.9 dB nominal) |

- **Gain and noise do not depend on the ground inductance** (0.03 dB): the stage is differential and the ground wires
  carry no signal current.
- **Common-mode stability does.** With any real supply / ground return the common-mode input resistance of this
  generic stage is negative around 0.4 GHz (rail decap resonating with the bond inductances). This is the mechanism
  the LNA review already found; it is a property of the package that the LNA must be designed against (common-mode
  damping, rail series resistance, decap value). The site choice changes it by 3 ohm only.
- **New: ground-bond current couples magnetically into the RF input pair as a differential signal.** Ground bond 71
  is 211 um from RF_RX_P and 422 um from RF_RX_N: mutual 0.57 against 0.28 nH. Every volt of die-VSS bounce drives
  V / (j w L71) through bond 71 and induces (0.57 - 0.28) / 2.31 = 0.124 V between the two RX wires. Summed over the
  ground bonds: -18.3 / -16.0 / -14.4 dB (magnitudes added), with the supply bonds too -15.2 / -12.4 / -10.1 dB. No
  LNA common-mode rejection helps: it arrives as a differential input. The residual with all coupling removed is
  -37 dB (2.7 % length difference of the two RX wires).

## 4. Site options for RF_RX (pairs must stay on adjacent sites: 65/66, 67/68 or 69/70)

Bounce conversion = sum over bonds of |M(P,k) - M(N,k)| / L(k); min / nom / max. LO coupling = differential-to-differential
mutual from the external-LO pad pairs.

| Option | Ground bonds only (dB) | Ground + supply bonds (dB) | Largest single term (nom) | AUX_CLK / REF_IN pair to RX pair (pH, nom) | South-edge host wires 1-8, sum (pH, nom) |
|---|---|---|---|---|---|
| A, today: RX 69/70, BB_I 67/68, BB_Q 65/66 | -18.3 / -16.0 / -14.4 | -15.2 / -12.4 / -10.1 | GND 71: 0.124 | 2.2 / 0.9 | 33 |
| **B: RX 67/68, BB_I 69/70**, BB_Q 65/66 | -30.9 / -25.8 / -19.9 | -25.3 / -20.1 / -14.3 | GND 71: 0.027 | 6.1 / 2.2 | 18 |
| C: RX 65/66, BB_Q 67/68, BB_I 69/70 | -28.0 / -24.0 / -19.4 | -17.2 / -14.4 / -11.7 | PWR_AUX_1 64: 0.116 | 22 / 6.3 | 10 |

**Proposed: option B.** RF_RX moves two sites north to 67/68, BB_I takes 69/70. Gain: 10 dB less ground-bounce pickup
at nominal (5.5-12.6 dB over the bounds; 19 dB in the bench where all bonds see the same bounce), both RX wires get
identical signal neighbours, and the pair is 422 um further from the south-west corner where the host-link output
wires land. Costs:

- External-LO fallback: coupling from the AUX_CLK / REF_IN pads to the RX pair rises by 8.9 / 7.8 dB. On the existing
  leak table (L1 map, 4 Vpp: +11.2 / +2.4 / -12.7 dB margin) that is about +2.3 / -6.5 / -21.6 dB at 4 Vpp and
  +14.3 / +5.5 / -9.6 dB at the decided 1 Vpp drive. The on-chip LO is not affected.
- The LNA and its pad cell move 422 um north on the west edge; the BB_I taps route 422 um further.
- `pad_rf_rx` and `pad_bb_i` are the same master (`pad_rf_pair`): no pad cell changes.

## 5. What does not exist

- No AGND_RX pad, no source pads, no ground split in the pad ring. `analog/pads/agnd_pad.py` (one-pad runner-up for
  site 71) is unreviewed and unpublished. Taking bond 71 off die VSS would remove the largest coupling term of option A
  (0.124 of 0.158) but costs the ground bond nearest the LNA and one clamp cell; option B gets the same benefit
  without either.
- Not modelled: on-die VSS ring impedance, the real currents in each bond (the conversion figures are per volt of
  bounce, equal on all bonds), capacitive coupling, the glob-top, any EM solve.
