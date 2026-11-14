# Off-chip passives pass (2026-11-14)

Question: how much of the die-fit shortfall (1.3-2.3 mm2 before routing/decap risk, `die-fit.md`) can be closed by
moving on-chip PASSIVE functions, and the active circuits that exist only to make or trim them, to passives on the
carrier? Rule: only passives, the FPGA and a fallback LNA may be off-chip; no capability, mode or rate may be lost.

Analysis and proposal only. No design file changed, no circuit simulation (hand calculations; one read-only KLayout
layer measurement, one job, one thread). Work dir `scratch/reviews/offchip-passives/`.

STATUS: complete, independent review applied (section 9). `wafer-space-answers.md` did not exist when this was
finalised: case A / case B are both given (section 7).

Inputs that arrived during the pass and are treated as baseline:
1. Per-mode idle pins: "one spare pad" is the wrong budget; a passive needed only in a mode that leaves pads idle can
   use those pads (section 3).
2. Per-application carriers are fully acceptable (MANDATE "Per-application carriers"): a pad may carry different
   functions on different carriers. A column says whether an item also works on one universal board.
3. Packaging is the wafer.space COB only. Case A = no parts on the COB (nearest part on the carrier, >= 6.5 nH per
   leg). Case B = passives allowed on the COB near the die (section 7).

## 1. Bottom line

**Off-chip passives close 0.15-0.45 mm2 of the 1.3-2.3 mm2, not more.** The passives on this die are small. Measured
on the layouts, all MIM, MOS-capacitor, poly-resistor and inductor marker area outside the pads and the QVCO tank is
0.33 mm2 in total, and most of it either must stay at the circuit (reference reservoir, filter capacitors inside an
active filter, RF tanks) or is drawn above devices and frees nothing. Three things are real:

| | mm2 | condition |
|---|---:|---|
| LO loop-filter capacitor C2 (490 pF MOS capacitor) to the carrier | 0.15 | two pads idle in RF modes; Kelvin return |
| WTX_EXT fallback input moved onto the USB pad pair (pad family deleted; not a passive, a consequence of per-application carriers) | 0.15 | USB and wired are different carriers |
| QVCO regulator hold capacitors and megohm resistors to the carrier (this IS die-fit lever 11, not additional to it) | 0.10-0.15 | three pads; regulator never built |

**USB is not in this category.** The USB passives (pull-ups, pull-downs, 45 ohm terminations, LS Miller capacitors)
measure about 0.005 mm2 on the die. USB costs about 0.58 mm2, but that is the ESD shell of its pad (0.255), its
drivers (0.098), `pt_usb_txdrv` (0.031), the bias DAC and its share of `pt_detect`: none of it is a passive, and the
terminations and pulls cannot leave the pad without a switch that is itself the FS low-side driver (section 5.1).

**Decap, terminations, RF inductors: nothing.** The board cannot replace any of the 5.4 nF decap plan (the plan exists
because of the bond inductance, section 5.4). External termination breaks the 2.5-3.24 Gb/s rates in case A (section
5.2). Every RF inductor is smaller than one bond wire (section 5.5).

What the pass does deliver besides area: a pad plan for the LO passives that the design of record already needs but
never budgeted (`LO_CEXT` and its Kelvin ground: the regulator fails its rejection lines without the external
capacitor), two freed pad sites, and a per-mode pin table that shows 10-14 signal pads idle in every mode.

## 2. Passive-device inventory (measured)

`offchip-passives/passive_area.py` -> `passive_area.csv` (76 layouts; read-only; markers: MIM top plate 75/0,
RES_MK 110/5, MOS_CAP_MK 166/5, IND_MK 151/5; merged area per top cell). Limits of the method: MOS capacitors drawn as
ordinary transistors (`pt_pll_vreg2`, `pt_lo_vreg` design) and metal-finger capacitors (ADC CDAC) are not marked, so
those were taken from the generator/README device lists; `core_support` has no published per-block GDS in `generated/`
(vendored biasgen, v5 abstract).

| block | outline mm2 | MIM | poly R | MOS cap | spiral | what the passives are | can it leave the die? |
|---|---:|---:|---:|---:|---:|---|---|
| `pt_lc_qvco5` | 0.586 | 0.005 | 0.007 | 0.008 | 0.331 | tank spirals, varactors | no (2.4 GHz tank) |
| `pt_lo_lf` | 0.194 | 0.007 | 0.000 | **0.136** | | C2 489.6 pF (85 x 40 x 40 um MOS), C1 5.45 pF, C3 8.84 pF, R 10.38 k, R3 10 k | **C2 yes** (section 4, OCP-1) |
| `pt_refbuf` | 0.117 | 0.055 | | | | 100 pF VREF reservoir, 10 pF compensation | no: SAR reference charge at ns scale, behind >= 2.2 nH |
| `pt_bbfilter_i/q` | 0.342 each | 0.034 each | 0.003 | | | active-RC filter capacitors | no: capacitors sit inside the amplifier loops; the block is gain + filter, 90 % of it is not passive |
| `pt_lna`, `pt_rxmix_i/q` | 0.043 / 0.035 | 0.009 each | | | | coupling / TIA capacitors (above devices) | no |
| `pt_adc_i/q` | 0.578 | 0.008 | | | | decoupling; CDAC is metal fingers | no |
| `pt_lo_ext`, `pt_lo_pfdcp`, `pt_lo_mmd` | 0.155 / 0.124 / 0.361 | 0.004 / 0.000 / 0.001 | 0.001 / 0.004 / 0 | | | coupling, bias | no (small) |
| `pt_pll_vreg` (single) / `vreg2` | 0.239 / 0.173 | | 0.006 / 0.001 | (unmarked: gate 0.030 + outputs 0.006) | | gate hold capacitor, output capacitors | gate capacitor possible, 0.03, rejected (section 6) |
| `pt_lo_vreg` (never built, 0.30) | | | (0.059) | (0.112) | | hold capacitors CG1 102 pF, CG2 153 pF, CO 51 pF, 2.6 Mohm filter resistors | **yes, partly** (OCP-3) |
| `term_buffer` | 0.075 | 0.002 | 0.000 | | | compensation | no passive to move; the buffer itself: section 5.2 |
| `pt_detect`, `pt_ctle`, `pt_termination`, `pt_vthdac`, `pt_rxlevel` | 0.173 / 0.133 / 0.048 / 0.024 / 0.013 | 0 | 0.0009 / 0.0002 / 0.0002 / 0.0002 / 0.0003 | | | ladders, degeneration | nothing to move |
| `pt_wiredtx`, `pt_usb_txdrv`, `pt_wrx_cap`, `pt_slicer`, `pt_cdr`, rings, `pt_ptrim`, clocks | | 0 | 0 | | | none marked (20 pF HS_PBIAS bypass in usbdrv is a transistor capacitor) | no |
| `pad_wirepad` (USB) | 0.748 bbox | 0.0204 | 0.0209 | | | ESD RC triggers + USB passives | USB part = 0.0030 MIM + 0.0023 R more than the bare protection cell (`pad_single_leg`: 0.0174 / 0.0186) |
| `pad_hspad` | 0.449 bbox | 0.0223 | 0.0190 | | | ESD + 2 x 4.9 pF AC-coupling MIM + termination | AC MIM 0.0049, needed for DC-coupled TMDS |
| other pad families | | 0.0174 | 0.0186-0.0189 | | | ESD RC triggers, bleeds | no |
| POR | | 7.2 pF MIM | | | | hold-off capacitor | 0.002: no |

Sum of marker area outside pads and QVCO: MIM 0.167, resistors 0.011, MOS capacitor 0.136 (+ about 0.15 unmarked in
the two regulators) mm2. The only large, free-standing capacitors are C2 of the LO loop filter and the regulator
hold capacitors.

## 3. Per-mode pin usage and carrier set

Sources: `spec/contract.json` `bond_map_current` (PC-18 applied: POR strap on `bidir[16]`, `bidir[17]` held spare,
AGND_RX on the two west openings without a finger), `integration/top/pt_chip.conn`, `mode-walk.md` section 6,
`spec/exclusive-engine-policy.md` (RF and wired payload are never active together: user decision 2026-09-22).

Signal pads: west RF_RX P/N, BB_I P/N, REF_IN P/N, AUX_CLK P/N, BB_Q P/N, RF_TX P/N (12, custom); east WIRE_RX P/N,
strap, spare, USB DP/DN, WIRE_TX P/N, WTX_EXT P/N, WMON, TLP site (12); north H2D[0:9] + clock, CLK_OBS, DBG_OBS0/1,
ATB0/1; south D2H[0:9] + clock, SPI x 4, RESET_N.

U = used, d = debug / observation only, f = fallback only, - = idle (pad cell powered down or high impedance).

| pad(s) | RF RX, on-chip LO | RF TX | duplex | RF, external-LO fallback | wired SATA/PCIe/DP/1000BASE-X/TMDS, RX+TX | 100BASE-TX | USB LS/FS/HS | SPI bring-up |
|---|---|---|---|---|---|---|---|---|
| RF_RX P/N | U | - | U | U | - | - | - | - |
| RF_TX P/N | - | U | U | U/- | - | - | - | - |
| REF_IN P/N | U (reference) | U | U | U (LO I) | U (reference) | U | U | - |
| AUX_CLK P/N | **-** | **-** | **-** | U (LO Q) | U for HDMI RX / CDR fallback (forwarded clock, CP4-3), else - | - | - | - |
| BB_I, BB_Q (4) | d / f (external ADC) | d (DAC injection) | d | f | - | - | - | - |
| WIRE_RX P/N | **-** | **-** | **-** | - | U | U | - | - |
| WIRE_TX P/N | **-** | **-** | **-** | - | U | U | - (silent) | - |
| USB DP/DN | **-** | **-** | **-** | - | **-** | **-** | U | - |
| WTX_EXT P/N | **-** | **-** | **-** | - | f (<= 1.6 Gb/s external data) | f | - | - |
| WMON | - | - | - | - | d | d | d | - |
| spare `bidir[17]` | - | - | - | - | - | - | - | - |
| H2D[0:9] | - (D2H only; outputs in RX2) | U | U | as RX/TX | U | U | U | - |
| D2H[0:9] | U | - (status only) | U | as RX/TX | U | U | U | - |
| SPI, RESET_N, strap, CLK_OBS, DBG_OBS0/1 | U | U | U | U | U | U | U | U |
| ATB0, ATB1 | d | d | d | d | d | d | d | d |

Idle signal pads per mode family: RF with the on-chip LO: 10 east pads + AUX_CLK pair (12). Wired: 10 west pads
(RF_RX, RF_TX, BB_I, BB_Q, AUX when no forwarded clock) + USB pair. USB: all west except REF, WIRE_RX, WIRE_TX,
WTX_EXT (18).

Natural carrier set (each carrier always has: supply + trim, SPI, RESET_N, strap jumper, REF_IN source, ATB0/1,
CLK_OBS, DBG_OBS0/1 to test points and the FPGA):

| carrier | modes it must support together | pads whose normal function it never uses |
|---|---|---|
| RF (primary, on-chip LO) | RX, TX, duplex; BB taps for debug; switch at run time between RX/TX/duplex | all east wired pads (WIRE_RX, WIRE_TX, USB, WTX_EXT, WMON), AUX_CLK pair |
| RF fallback population (same board, other parts fitted) | external LO on REF + AUX, external ADC/DAC on BB, board LNA | east wired pads |
| wired high-speed (per connector family: SATA / PCIe / DP / SFP / HDMI) | RX + TX full duplex, WTX_EXT fallback, WMON, forwarded clock on AUX (HDMI) | RF_RX, RF_TX, BB_I, BB_Q, USB |
| 100BASE-TX | TX + RX through magnetics | RF pads, BB, USB, WTX_EXT, AUX |
| USB (device or host population) | LS / FS / HS, chirp, WMON | RF pads, BB, AUX, WIRE_RX, WIRE_TX, WTX_EXT |
| bring-up / characterization | SPI, ATB, observation; everything else by jumper | - |

Rules that follow for sharing a pad between an internal node and its normal function:
- The node is used only on carriers where the pad's normal function is not: the passive is simply not fitted on the
  other carriers. One universal board is then possible only with a jumper or a second footprint per shared pad.
- High-impedance or DC-sensitive nodes cannot use a custom pad family: the stress-safe shunt of every custom family
  draws < 1 uA only up to 1.65 V and 0.1 mA at 2.5 V, 1.3 mA at 3.0 V (pads README "Swing and loading cost"). They
  need a provider analog cell (as ATB0/1) or a low-impedance node.
- Every internal node brought out crosses to a pad of another island; the pad side is powered from the always-on
  ring, the switch gate needs the island's `ISLAND_OFF` clamp, and the node sees HBM through the pad's primary diodes
  (2 kV tier, residual <= 1.33 A at the pad): each row below states the series element that protects it.

## 4. Candidates that survive (ranked by area freed x confidence)

Area source: die-fit ledger v2 (`die-fit/ledger.csv`), scenario B/C values. "Pads" classes: none / mode-idle (named) /
new. Owner in brackets.

### OCP-1. LO loop-filter capacitor C2 to the carrier (0.15 mm2, confidence M) [LO]

- Today: `pt_lo_lf` 0.194 mm2, 0.136 of it is C2 = 489.6 pF as 85 n-well MOS capacitors between node X and VSS
  (`analog/timing/lo_lf.spice`). R = 10.38 k sits between the charge-pump node CP and X; C1, R3, C3 stay.
- Proposal: bring X to a pad; C2 = 470 pF C0G 0402, +-5 %, on the carrier, returned to a second pad `LO_AGND` that is
  tied on the die to the varactor / charge-pump ground (Kelvin, no supply current). On-chip remainder: C1 + C3
  (0.007 mm2 of MIM), two resistors, a 200 ohm series resistor and secondary clamp at the X pad, about 5 pF at X:
  0.02-0.03 mm2. Routing two shielded wires across the die (if the pads are east): about 0.02 mm2 of channel.
  **Net freed 0.14-0.15 mm2**, 0 mA.
- Why X and not CP or VTUNE: X is the node behind R. Pad, bond, trace and connector capacitance (3-8 pF) only add
  1-2 % to C2, and series resistance of the route adds to R (100 ohm = 1 %). The bond inductance (8 nH per leg, 16 nH
  loop) resonates with 470 pF at 58 MHz, 200 times the loop bandwidth, and R (10 k) with C1 isolates CP from it.
- Why the Kelvin return is not optional (hand calculation): a capacitor returned to carrier ground puts the
  chip-to-carrier ground difference directly on X above 31 kHz (1/2 pi R C2), and the loop does not suppress it
  between its 300 kHz bandwidth and the 1.8-2.8 MHz poles of C1 and R3/C3. Spur = 20 log(Kv V / 2 fm). With Kv =
  90 MHz/V and the PA-envelope current of integration-m1 F5 (3-18 mA at 1 MHz) through about 20 mohm of shared ground
  path: 60-370 uV, spur -51 to -36 dBc at 1 MHz (limit -80 dBc, or -61 dBc if the LO owner's 30 uV reading holds).
  With the Kelvin return only the stray capacitance of the X wiring to carrier ground converts ground noise: 5 pF /
  490 pF = 1 %, -40 dB: -91 to -76 dBc at Kv 90, 7 dB worse at Kv 200. Passes the -61 dBc reading everywhere and the
  -80 dBc reading except at the pessimistic envelope. On the die C2 is referenced to the same ground as the varactor
  and this term is zero: that is what gets worse.
- Other costs: leakage. Charge pump 100 uA, reference 50 MHz: 10 nA of pad + board leakage is a 2 ps static phase
  offset (today -60 to -158 ps from the pump itself): harmless, but only on a provider analog cell (nA) with a guard
  trace and clean board; a custom pad (10 uA onset at 2.1 V, VTUNE is centred at 2.1 V) is excluded. ESD: X is a new
  externally reachable node; HBM current into the loop is limited by R = 10.38 k (0.6 mA at a 6-7 V clamp). C2 is
  then linear (the MOS capacitor is valid only for 0.3-3.0 V) and +-5 % instead of +-15 %, and the loop bandwidth can
  be changed per carrier: a gain. Loss of self-containment: an RF carrier without the capacitor has no LO loop (the
  loop then has only C1: unstable). The external-LO fallback does not need it.
- Pads (class: mode-idle). Two pads idle in every RF mode, both provider analog cells:
  (a) the held spare `bidir[17]` + ATB1 as `LO_AGND` (ATB1 then unavailable while the loop is closed; ATB0 remains);
  (b) with OCP-2: the two freed sites `bidir[22]`/`[23]` rebuilt as provider analog cells (preferred, a neighbouring
  pair, nothing lost);
  (c) not AUX_CLK (custom family, leakage), not ATB as X (the ATB bus spans the die and has 79 leaves).
  All east pads are 3 mm from the QVCO; the wired islands they pass are off in RF modes. Coupling of a 3.3 V digital
  net into X through 10 fF is 67 uV at 78 MHz, filtered by R/C1 and R3/C3 by more than 60 dB: negligible.
- Universal board: yes for (a) and (b): the pads have no other function.
- Capability check: RX, TX, duplex use the on-chip LO exactly as today (same R, C1, C3, same C2 value). External-LO
  fallback unchanged. Wired and USB carriers: pads unconnected, LO island off.
- Verification: loop phase margin and noise with 470 pF +-5 % and 3-8 pF extra at X (existing `loop_design.py` grid);
  ground-difference spur with the m1 PDN model (new: inject the m1 ground-bond voltage between `LO_AGND`-referred and
  carrier-referred capacitor return); HBM on the X pad with the loop filter and charge pump attached; leakage at
  32 C.

### OCP-2. WTX_EXT fallback input on the USB pad pair; `pad_wtx_ext` deleted (0.151 mm2, confidence M) [pads, wired TX]

- Not a passive: a pad-ring consequence of per-application carriers. USB and the wired lane are never on the same
  carrier and never active together (USB HS uses `pt_wiredtx` as its serializer with the WIRE_TX pad silent).
- Today: `pad_wtx_ext` = one `pad_rf_pair` (310 x 487 um in the core, 0.151 mm2), `rx_wtx_ext` (`pt_diff_clk_rx`,
  0.022) and `pt_wtx_fallback_control`. The USB pad `pad_usb` (bonds 24/25) is the neighbour of WIRE_TX (bonds 28/29)
  and already has a 45 ohm per leg termination, an RX tap (`USB_RX_P/N`) and `wmon_sel` attached.
- Proposal: delete `pad_wtx_ext`; feed `rx_wtx_ext.INP/INN` from `USB_RX_P/N` (the pad's existing RX outputs, level
  divider bypassed). On a wired carrier the fallback serial data enters on the USB pads through the B12 AC capacitors
  (100 nF 0402, already a board obligation). Frees `bidir[22]`/`[23]` (two bonded provider sites, contacts 50/49 region).
- What gets worse: the USB pad loads the fallback input with 2.34-2.35 pF per leg instead of about 1 pF: with 45 ohm
  on-die termination and a 50 ohm source the pole is at 2.9 GHz, against 1.6 Gb/s maximum (B12): acceptable on paper,
  not simulated. The receiver was benched on the rf_pair cell (WT28): rerun on the wirepad model, including the
  termination to `TERM_VCM` (must be the 1.2 V or VSS mode with AC coupling) and the P/N swap of `rx_wtx_ext`. One
  more load on `USB_RX_P/N` (the published USB disabled-loading limit of 2.7 pF has 0.35 pF of margin; the diff_clk_rx
  input must be checked against it, or switched). A universal board that offers USB and the WTX_EXT fallback from one
  connector set needs a jumper pair.
- Capability check: WTX_EXT fallback 0.5-1.6 Gb/s kept (wired carrier); USB LS/FS/HS kept (USB carrier); WMON
  unchanged. Lost: WTX_EXT fallback and USB at the same time on one carrier (no mode uses both; USB HS has no WTX_EXT
  path today).
- Not a double count: die-fit lists the WTX_EXT group only as a user decision to drop a fallback (5.1 item 4);
  AP4-7 (lever 1) moves BB_I, BB_Q, WMON, not WTX_EXT.
- Verification: `wtx_ext_rx` bench on the extracted wirepad + COB channel at 0.5 / 1.0 / 1.6 Gb/s, 300-800 mVpp;
  USB HS eye and disabled loading with the extra tap; pad-exclusion rule (USB drivers off when the fallback is used).

### OCP-3. QVCO regulator: hold capacitors and megohm resistors to the carrier (0.10-0.15 mm2, confidence L) [LO, user]

- This is die-fit lever 11 with a pad plan; do not add it to lever 11.
- Today (`scratch/lo-ap4/vreg2/NOTES.md`, never built, ledger 0.30 mm2 L): two native followers; gate hold
  capacitors CG1 102 pF and CG2 153 pF behind 2.6 Mohm, output 51 pF; cost split hold/output capacitors 0.112,
  pass devices 0.12, resistors 0.059. **The design of record already needs an external 10 uF on VOUT (pad `LO_CEXT`)
  and a Kelvin ground at that capacitor (power-delivery.md 5.1 "Ground"); neither pad exists.** Without the capacitor
  every rejection line below 20 MHz fails.
- Proposal: (1) give `LO_CEXT` and `LO_AGND` their pads (enabler for the regulator as designed, no area);
  (2) move CG1 and CG2 to the carrier as 100 nF C0G/X7R each, returned to `LO_AGND`, and reduce the filter resistors
  from 2.6 Mohm to about 2.6 k (same corner): hold capacitors 0.08 of the 0.112 and nearly all of the 0.059 of
  resistor go: **0.10-0.15 mm2**. Keep 10-20 pF per gate on the die for > 300 MHz.
- Expected electrical effect (hand calculation, not simulated): rejection per stage is limited by CG / Cgd (100 pF
  against 9 pF: 21 dB). With an external capacitor behind 8 nH the gate impedance at 78.125 MHz is 3.9 ohm against
  227 ohm of Cgd: 35 dB per stage, better than today; below 10 MHz better still; above about 300 MHz worse unless
  the on-die 10-20 pF stays.
- Pads (class: mode-idle, four in total with OCP-1 sharing `LO_AGND`):
  `LO_CEXT` + `LO_AGND` on the AUX_CLK pair (west, next to the QVCO and `pt_lo_ext`; idle whenever the on-chip LO
  runs; a 10 uF capacitor and a ground do not mind the custom pad's leakage). Each needs a switch of <= 1 ohm
  (PMOS about 3 mm for VOUT, NMOS 0.5 mm for ground: 0.005 mm2) that adds 0.5-3 pF to the pad in the external-LO
  fallback: the Q leg of the external LO loses level against the I leg (to be absorbed by B31 / BP-7 level adjustment
  per pair; not shown). G1, G2: provider analog pads (leak nA; node at 2.7-3.0 V excludes custom pads): east freed
  sites / spare, 3 mm away.
- What gets worse: regulator output distance. NOTES bounds: bond/trace 2 nH +3 dB, 5 nH -4 dB, 20 nH -9 dB at
  78.125 MHz; the model used 3 nH; case A is 6.5-8 nH: about 5 dB less than the tables at 78.125 MHz (LO21 basis
  44.8 dB -> about 40 dB against 40). Two more high-impedance nodes on bond wires; ESD on gate nodes of 6 V native
  devices (series 2.6 k helps). The external-LO fallback carrier cannot also carry the regulator capacitors on AUX
  (different population).
- Capability check: QVCO regulated in RX/TX/duplex; BYP mode unchanged; external-LO fallback on its own population.
- Verification: the owner's `bench.py` with the case-A channel on VOUT, G1, G2; ground-difference injection as for
  OCP-1; HBM; stability of the 145-285 Hz loop with 100 nF gate capacitors.

### Smaller items (kept for completeness, not counted in the totals)

| ID | item | mm2 | pads | why small / condition |
|---|---|---:|---|---|
| OCP-4 | FS/LS single-ended USB receivers as FPGA inputs through 2 x 1 kohm (0402, 1 %) | <= 0.01 (part of `pt_detect`) | none (FPGA pins) | 1 k + 8 pF = 8 ns against an 83 ns FS bit; 1 k in parallel with 45 ohm changes the HS impedance by 4 %. USB carrier only. Size inside `pt_detect` not separable from the layout; owner to say. |
| OCP-5 | ADC VCM: external 100 nF instead of the booked VCM buffer | 0.003 | ATB0 (refbuf OVR path exists) | only low-frequency; kick charge still needs the on-die path. |
| OCP-6 | Precision bias resistor REXT (12.1 k 0.1 %) on an ATB/bias-override pad | 0 | existing `pt_bias_ext` taps | no area: the biasgen is vendored and trimmed by `idac2` code. Gain is accuracy (+-20 % -> +-1 %), a risk reduction for die 1, not area. |

## 5. Looked at and rejected (with the number that decides)

### 5.1 USB

| function | on-chip today | external alternative | verdict |
|---|---|---|---|
| 1.5 k pull-ups (P and N), 15 k pull-downs | poly resistors + switches in `pad_wirepad`; 0.0023 mm2 of resistor for all USB resistors together | 1.5 k 1 % to an FPGA GPIO (classic attach control), 15 k fixed on a host carrier | possible, frees < 0.002 mm2 and costs FPGA pins; leaves the chip unable to attach by itself. **Not worth it.** |
| 45 ohm HS terminations + 3-bit trim + calibration (PD43) | 16 x 1.3 um poly per leg; the switch bank to `TERM_VCM` is also the FS/LS low-side driver | 45.3 ohm 1 % on the carrier | **No.** It must switch off in FS/LS (a 45 ohm to ground holds the line at 0 V against the 1.5 k pull-up) and the switch is on the die anyway; a series resistor instead would sit between the HS current source and the line. Area freed about 0. Calibration uses the existing bias DAC, nothing is deleted. |
| LS slew (Miller capacitors, PD47) | about 0.003 mm2 of MIM | capacitors on D+/D- | **No.** 75-300 ns edges need the capacitor at the driver gate, not 150 pF on the line (that gives 6 ns with a 40 ohm driver and breaks FS/HS on the same carrier). |
| HS bias DAC bypass (20 pF in `pt_usb_txdrv`) | transistor capacitor to the pad's VDD | external | **No.** It must be referenced to the VDD at the HS sources (2 % of amplitude per 20 mV of rail difference). |
| detector reference dividers | 0.0009 mm2 of resistor in `pt_detect` | - | nothing to move. |

So the USB pad family does not shrink through passives. What does shrink the USB-related area is OCP-2 (it reuses the
USB pad for a second function) and, outside this pass, the `pt_detect` redesign (AP4-1).

### 5.2 Wired RX / TX

| function | finding | verdict |
|---|---|---|
| 50/100 ohm RX termination and its trim | resistors are in the pad (4-bit segments, a few hundred um2). Case A: a termination on the carrier leaves 6.5 nH + 5-6 mm of 87 ohm trace + 1 pF pad unterminated behind it: resonance 1/(2 pi sqrt(6.5 nH x 1 pF)) = 1.97 GHz, +9 dB at 1.6 GHz (the 3.24 Gb/s Nyquist), +1 dB at 625 MHz. | **No** for 2.5-3.24 Gb/s; possible at <= 1.25 Gb/s but frees nothing. |
| `pt_termination` (0.048: TERM_VCM 1.2 V, HS TERM_VCM 0.45 V, VBIAS, USB ground switch) | active sources, 21k um2 used of the outline; the repack is AP4's | no passive substitute in case A. Case B: section 7. |
| TX termination buffer `term_buffer` (0.075, target 0.045) + `pt_txpad_bias` (0.0125) | a 1.65 V source for the TX terminations. A passive substitute is a Thevenin pair per leg (100 ohm to 3.3 V + 100 ohm to ground, 33 mA static for the pair) at the pad. | **Case A no** (same resonance argument as RX: Q = 66 ohm / 25 ohm = 2.6 with only the external load, +8 dB at 1.6 GHz). Case B: section 7. |
| on-die AC coupling (2 x 4.9 pF MIM in `pad_hspad`) | 0.0049 mm2 of MIM; board AC capacitors are already mandatory (B23) | keep: it is what lets a DC-coupled TMDS line (3.3 V common mode) reach the CTLE bias. |
| CTLE zero/pole, detect thresholds, `vthdac` | 181 / 902 / 207 um2 of resistor | nothing to move. |
| steering buffers | already replaced by the CML pre-drivers (die-fit R6) | - |

### 5.3 Loop filters, references, bias

| item | finding | verdict |
|---|---|---|
| ring PLL loop filters (CDR, TX: R 20 k, C1 8.8 pF, C2 0.9 pF) | < 0.004 mm2 each | no. |
| `pt_pll_vreg2` gate capacitor (30,000 um2) | 0.03-0.04 mm2 possible, wired carrier, needs a provider pad on the west side 3 mm away + Kelvin, on a 2.7 Mohm node | rejected: 0.03 mm2 against two pads and a megohm node on a bond. |
| `pt_refbuf` 100 pF reservoir (0.055 MIM) | the SAR draws its reference charge in ns; 2.2 nH of bond is 14 ohm at 1 GHz | no. External VREF force through ATB0 already exists for debug. |
| bandgap / biasgen capacitors (4 x 30 pF MIM), POR 7.2 pF | vendored cells, capacitors above or beside devices, 0.015 mm2 gross | no: shared infrastructure, most conservative design (MANDATE "No dead chip"). |
| `pt_bbfilter` capacitors (0.034 each) | inside the active-RC loops; an external LC filter (B20) needs 8 pins and still needs the gain stages | no. Idle east pads exist in RF modes, but 3 mm of baseband routing through four more pads for 0.07 mm2 of MIM that sits above the amplifiers frees nothing. |

### 5.4 Decap

None of the 5.4 nF plan and none of the 0.39 mm2 bank can move to the board. Reasoning from `integration-m1.md` (F4,
section 7) without re-simulation: the supply loop from the die to the first board capacitor is 0.5 nH (0.4-0.65; 18
bonds in parallel plus strip-capacitor mounting 1.2-2.6 nH each). The plan's capacitance is sized against that
inductance: the anti-resonance sqrt(1/LC) lands at 78-95 MHz for 4.4-6 nF, and the pk-pk ripple at the macro is set
by the characteristic impedance sqrt(L/C) = 0.3 ohm and the 0.77 nC per cycle. Board capacitance is on the far side
of L: it is already assumed (BP-4: eight 1 uF strip capacitors, mandatory; they act below about 30 MHz) and adding
more changes nothing above 30 MHz. Split of the plan by what the board could carry:

| part | nF | board-replaceable |
|---|---:|---|
| row fill, bond-site tiles | 0.9 | 0 |
| grid MIM | 2.0-3.0 | 0 |
| macro-edge bank | 1.5 | 0 |
| island-local | 1.16 | 0 for the GHz ring / serializer pulses; the < 30 MHz part is already the strip capacitors |

Case B does not change this: the bonds (2.2-3.2 mm, 1.8-3.2 nH each) stay.

### 5.5 RF

| item | on-chip | off-chip alternative | verdict |
|---|---|---|---|
| LNA tank spirals (2 x 0.036-0.057 mm2, 1.35 nH) | | bond wire is >= 1.8 nH and the pad adds >= 0.7 pF: already above the whole tank at 2.45 GHz | no, both cases |
| LNA degeneration spirals (2 x 0.025, 0.47 nH) | | bond to a ground finger: 1.1-2.3 nH realisable; chain NF 4.7-6.9 dB (`rf-lna-p/NOTES.md` v8/lsx): rejected by the owner and the independent review (RFR-14) | no |
| LNA input match | board network + on-chip `ctrim` | carrier only: -1.9 dB of tolerance (NOTES l.92-98) | already off-chip; case B improves it (section 7), no area |
| TX balun / match | already on the board (B17) | | - |
| QVCO tank (0.331 mm2 of spiral) | | external tank through two bonds: 4-6 nH of bond in a 1-2 nH tank | no |
| T-coil reserve for WIRE_TX (0.068) | | bond inductance is on the wrong side of the pad capacitance | no |

### 5.6 Other pad-family sharing by carrier

| idea | saving | why not |
|---|---:|---|
| USB function on the WIRE_TX or WIRE_RX pad (delete `pad_wirepad`, 0.31-0.35) | 0.31-0.35 | the USB FS drivers add 2.3 pF to the pad; `pad_hspad` exists because 2.35 pF fails the 2.5-3.24 Gb/s return loss (PD21). A rate would be lost. |
| AUX_CLK function (external LO Q, forwarded clock) on the BB_Q pair (delete one `pad_refpad`, 0.195) | <= 0.044 after die-fit lever 1 | lever 1 puts BB_Q on a provider cell at zero core area; the merged pad would have to stay custom. Also loses external LO + external ADC together (the two-fault RX recovery). |
| BB_I and BB_Q single-ended on one pair | 0.151 | only if lever 1 fails; loses differential observation of the fallback RX path. |
| WMON on a BB or USB leg | 0.10-0.147 | already CP4-5 / AP4-7: not counted again. |
| characterization probe frames (0.335) | - | probe pads, not passives; die-fit lever 4. |

## 6. Totals and what it closes

| class | items | mm2 | pads |
|---|---|---:|---|
| no pad needed | OCP-2 (frees two sites) | 0.151 | -2 |
| mode-idle pads | OCP-1 | 0.14-0.15 | 2 provider analog pads idle in RF modes (`LO_X`, `LO_AGND`) |
| mode-idle pads, not additional to die-fit lever 11 | OCP-3 | 0.10-0.15 | AUX_CLK pair by switch (`LO_CEXT`, shared `LO_AGND`), 2 provider analog pads (G1, G2) |
| genuinely new pad | none | 0 | |
| **new in this pass** | OCP-1 + OCP-2 | **0.29-0.30** | net 0 (two freed, two used) |
| with lever 11 realised through OCP-3 | | **0.39-0.45** | spare `bidir[17]` + one of ATB1 / WMON site for G1, G2 |

East provider analog sites available in RF modes after OCP-2: `bidir[22]`, `bidir[23]`, held spare `bidir[17]` (3).
Needed: `LO_X`, G1, G2 on provider cells; `LO_AGND` and `LO_CEXT` on the AUX_CLK pair. It fits without ATB1.
If the spare is given to the supply bond (PC-18 option P2), G1 or G2 needs ATB1 or OCP-3 stops at step (1).

Against the shortfall (packer, before routing / decap risk):

| scenario | shortfall | after die-fit levers 1-5 (`c-l6` stack) | + OCP-1 + OCP-2 (0.29) | + OCP-3 (lever 11) |
|---|---:|---:|---:|---:|
| C (all targets met) | 1.35-1.5 | 0.19 (0.83 flow-first) | about -0.10 (fits; 0.54 short flow-first) | -0.20 to -0.25 |
| Cr (backed targets) | 1.61-1.75 | 0.26 | about -0.03 | -0.13 to -0.18 |
| B (staged as measured) | 2.14-2.3 | 0.81 | 0.52 | 0.37-0.42 |

Alone: 0.3 mm2 (0.45 with OCP-3) of 1.3-2.3 = 13-23 % (20-35 %). Combined with levers 1-5 it turns scenario C and
Cr from 0.2-0.3 short to about zero or slightly positive in the densest packing; it does not rescue B, the flow-first
packings, or the unbooked risks (routing 0-1.0, decap tiles 0.15-0.47, island-local decap 0-0.29). These are area
sums: the packer was not re-run with the smaller `pt_lo_lf` and without `pad_wtx_ext` (the pad is an edge obstacle,
so its removal should place fully; `pt_lo_lf` is a mid-size block).

No double counting: OCP-1 touches `pt_lo_lf` (in no die-fit lever, no AP4 target, not in CP4); OCP-2 removes
`pad_wtx_ext` (die-fit lists it only as a decision to drop the fallback; AP4-7 / CP4-5 concern BB and WMON);
OCP-3 = lever 11.

## 7. Case A and case B

Case A (assumed today: no part footprints on the COB; first part on the carrier past 5-6 mm of 87 ohm trace, a via
and the connector: >= 6.5 nH and about 0.9 pF per leg): everything in sections 4-6 is case A. OCP-1 and OCP-2 do not
depend on distance. OCP-3 loses about 5 dB at 78.125 MHz against the owner's tables.

Case B (0201/0402 passives allowed on the COB within 1-2 mm of the fingers: bond 1.8-3.2 nH + about 1 nH):

| item | what changes | extra area | confidence |
|---|---|---:|---|
| OCP-3 `LO_CEXT` | 3-4 nH instead of 6.5-8: the owner's modelled rejection (44.8-51.4 dB at 78.125 MHz) holds | 0 | M |
| TX termination as a Thevenin pair per leg on the COB (4 x 100 ohm 1 % 0201, 100 nF), replacing `term_buffer` + `pt_txpad_bias` | 3 nH + 1.5 pF resonates at 2.4 GHz; peaking at 1.62 GHz with only the external 25 ohm load about +4 dB, needs the TX owner's eye check at 3.24 Gb/s; 33 mA static in the resistors (board power, not die) | 0.06-0.09 | L |
| RX `TERM_VCM` sources (part of `pt_termination`) replaced by COB resistors to ground for the AC-coupled protocols | TMDS (DC-coupled) and USB (ground switch) still need the on-die paths | 0.01-0.02 | L |
| LNA input match on the COB (RFR-13 / B18 / B25) | the match becomes buildable; chain NF better by 0.25-0.65 dB | 0 (risk, not area) | M |
| LNA / QVCO inductors, decap, USB, refbuf | unchanged: limited by the bond wire itself | 0 | H |

Case B total: **+0.07-0.11 mm2** at low confidence on top of case A, i.e. 0.36-0.41 (0.46-0.56 with OCP-3). The
value of case B is risk (LNA match, regulator rejection), not area.

## 8. Proposed board obligations (for `spec/board-requirements.md`; that file is not edited here)

| proposed ID | carrier | requirement |
|---|---|---|
| B49 (OCP-1) | RF | `LO_X` to `LO_AGND`: 470 pF C0G +-5 % 0402 (50 V), within 10 mm of the connector, both traces routed as a pair away from switching nets, guard trace at `LO_AGND` potential around the `LO_X` pad and trace, no test point, board leakage <= 5 nA at 3 V (cleaned, no flux under the part). Nothing else on either net. A second footprint (DNP) for a parallel part allows loop-bandwidth changes. |
| B50 (OCP-3 step 1) | RF, on-chip LO population | `LO_CEXT` (AUX_CLK_N contact) to `LO_AGND` (AUX_CLK_P contact): 10 uF X5R/X7R (>= 4.7 uF effective at 2.7 V bias), ESR <= 20 mohm, 0402/0603, within 3 mm of the connector; no connection of `LO_AGND` to carrier ground. The external-LO coupling capacitors (B3, 10 pF) are NOT fitted on this population, and vice versa. |
| B51 (OCP-3 step 2) | RF, on-chip LO population | G1, G2 each 100 nF C0G or X7R +-10 % to `LO_AGND`, guard as B49. |
| B52 (OCP-2) | wired | the B12 fallback data source and its two AC capacitors connect to the USB_DP/USB_DN contacts (was WTX_EXT_P/N); the USB connector, its TVS (B46) and series parts are not fitted on wired carriers. Universal boards: a 0 ohm jumper pair selects USB connector or fallback source. |
| B53 (carrier rule) | all | pads that carry an internal node on one carrier (`bidir[17]`, `[22]`, `[23]`, AUX_CLK pair) are left unconnected, without test points or stubs longer than 5 mm, on carriers that do not use them. |
| B10 change | all | `WTX_EXT` test point removed from the debug-site list. |

## 9. Independent review

See `offchip-passives/review.md`. Summary of what survived is appended below after the review.

## 10. Decisions that need the user

1. Accept two (OCP-1) or four (with OCP-3) pads that carry LO-internal nodes on the RF carrier, i.e. an RF carrier
   without those capacitors has no on-chip LO.
2. Use of the held spare `bidir[17]` (PC-18): supply-bond option P2, or an LO node (needed for OCP-3 step 2 without
   touching ATB1).
3. OCP-2: WTX_EXT fallback and USB can no longer be on one carrier without a jumper.
4. QVCO regulator: which basis holds (-80 dBc or the 30 uV / -61 dBc reading). With -61 dBc the Kelvin return of
   OCP-1 has 15-30 dB of margin and OCP-3 may reduce to a single follower stage (LO owner).
5. Case B: ask wafer.space whether the customer may add 0201 footprints on the COB within 2 mm of the fingers on four
   nets (WIRE_TX P/N, RF_RX P/N) and one pair (`LO_CEXT`/`LO_AGND`); worth 0.07-0.11 mm2 and the LNA match.

## 11. Files

- `offchip-passives/passive_area.py`, `passive_area.csv`: layer-marker passive area per layout (76 cells).
- `offchip-passives/candidates.csv`: one row per candidate (survivors and rejections).
- `offchip-passives/review.md`: independent review.
- Rows `OCP-1` .. `OCP-6` in `interface-changes.md`.

Not done: no simulation of any proposal; the packer was not re-run; `pt_detect` and `core_bias` were not dissected
(no per-function layout split available); the ground-path impedance used in OCP-1 (20 mohm) is a hand estimate from
the m1 bond and trace values, not a model output.
