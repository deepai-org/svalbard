# RF RX LNA closure, session Q (started 2026-11-18). Resume point for a successor.

Scratch: `scratch/rf-lna-q/` (scripts e1..eN, logs, `w/` work dirs). Predecessor: `scratch/rf-lna-p/NOTES.md`, review
`scratch/review-lna3/REPORT.md`.

## Pass limits (declared before the redesigned stage was simulated or laid out; not to be moved)
- Differential stability, every row: mu > 1, K > 1, min Re(Zin) with the real extracted mixers >= 1.0 ohm, 0.1-30 GHz (unchanged).
- Common-mode stability, every row: min Re(Zcm) >= 1.0 ohm, 0.1-30 GHz (unchanged, predecessor's limit). The LNA-disabled value
  (mode 'off') is reported next to it as the passive reference. A row that misses 1.0 ohm is a MISS even where the disabled
  network misses it too; such rows are labelled "passive floor" and go to the coordinator as a limit-definition request.
- Supply cases: (S1) no credit: supply/ground bond 0.25 / 1 / 2 nH, lossless, no decap; (S2) real PDN two-sided
  (spec/power-delivery.md): die decap 3-5.4 nF with 0.03-0.1 ohm, island switch 0.2-0.3 ohm, bond 0.25-1 nH, with and without
  100 / 500 pF on the island rail; (S3) undamped lossless island decap 100 / 500 pF and no die decap (predecessor's rows): kept
  as pass/fail rows, not downgraded.
- Currents: RX <= 19.0 mA, lobias <= 11.8 mA at EVERY envelope corner (12 corners), not only tt.
- Chain NF: on-chip <= 4.1 dB DSB (RF-RX-NFSYS 8 dB - 3.91 dB board budget) at tt, ss and the pessimistic view (extpp ss 32 C
  3.15 V), on the real COB channel with lossy carrier parts, with the LO as delivered (not the ideal square).
- LNA NF (band rows): <= 6.0 dB; extpp derated +1.5 dB <= 6.0 dB. S11 <= -10 dB over 2.395-2.4885 GHz.
- Layout: Magic DRC 0, KLayout DRC 0, LVS unique on the GDS read back from disk, with a failing negative control.
- Negative controls: CM bench must fail on the LNA with the tail AC-shorted to VSS, tank feed shorted to VDD, CM network open.

## What the half-done redesign (uncommitted diff found on 2026-11-18) was
- LNTA: pseudo-differential CS 450 um/leg, 10 ohm gate R, replica bias, cascode with current-steering attenuator, tank on two
  170 um spirals to VDD, 4-bit tank trim, bypass MIM, source pins for degeneration; benches moved to on-chip degeneration spirals.
- Sound: topology choice, on-chip degeneration, current-steering attenuator, benches (stability bench with real mixers, det chain).
- Not sound / unfinished: common mode (below); differential margin 0.61 ohm at ff with 10 ohm; tank trim bank far off centre for
  any larger coil; cascode "keep" switches were NMOS pass devices: the cascode gate clipped at VDD - Vth (vcas never applied);
  current 15.7-21.4 mA over corners (replica bias); board network unbuildable; evidence stale.

## Common-mode mechanism (e1-e5, e9, e10)
- Reproduced: extpr ff 32 C 3.35 V, extracted: Re(Zcm) -57 ohm at 1.12 GHz; schematic -108.
- Not the cascode gate, not the gate bias (e2: ideal AC grounds change nothing).
- Cause: the CM drain current of a pseudo-differential stage returns through the VDD and VSS bonds. Above the parallel resonance
  of the bond loop with the on-chip VDD-VSS capacitance (~10 pF from the mixers: 1.12 GHz at 2 x 1 nH) the chip ground moves
  against the board as a capacitive source impedance -> negative input resistance, up to where the on-chip degeneration
  (Ls/2) takes over (~2.3 GHz). Frequency and depth follow the bond L exactly (0.25 / 1 / 2 nH: 2.12 / 1.12 / 0.80 GHz).
- A tail alone leaves -Cgs*Ct/(gm*Cpad^2) ~ -2 ohm, flat in frequency (tail-node capacitance = capacitive degeneration).
- Fix = three parts, all needed (e3, e4): (1) tail current source (CM current small); (2) local return of the load current:
  tank centre tap `vtk` fed through ~12 ohm and returned to VSS by 20 pF, dump branch on vtk; (3) common-mode-only loss:
  0.3 pF from each RF pad to a common node, 60 ohm from there to VSS (differential: virtual ground, only pad C).
- Remaining by construction: an undamped lossless island decap without die decap (S3) still fails (-12 / -46 ohm at 0.34 / 0.16
  GHz); it passes with decap ESR >= 0.5 x sqrt(L/C) (100 pF: 2 ohm, 500 pF: 1 ohm) or with the real die decap behind the island
  switch. Passive floor above 16 GHz: 0.83-1.02 ohm (disabled LNA: 0.83).
