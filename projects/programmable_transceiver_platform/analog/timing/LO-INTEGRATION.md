# LO subsystem: pin list and connection intent for chip-top integration

LO/timing owner, 2026-11-13. Answers mode-walk rows MW-1, MW-2, MW-7, MW-19, MW-30 (LO part). Source of every pin
order: the `.subckt` line of the named netlist (checked today). If a netlist and this file disagree, the netlist wins
and this file is stale. Reviewed independently on 2026-11-13 (`scratch/lo-ap4/review/REVIEW.md`); its findings A1-A13 are folded in below.

## 0. Status, so nobody plans on more than exists

| Path | State | Usable on die 1 |
|---|---|---|
| External LO through the CML driver (`EXT=INT=CMLSEL=1`), board I on REF_IN, Q on AUX_CLK | extracted, 1.0-4.5 Vpp window at tt/ss/ff against a level criterion that MW-20 shows is not sufficient | **yes, the RF baseline, with reduced RX gain** (section 6) |
| External LO, passive path (`EXT=1`) | backup, fails ss/4.5 Vpp by 3 mV | bench only |
| On-chip synthesizer (QVCO + MMD + PFD/CP + filter) | every block laid out and extracted; closed loop passes the lock ladder except the slow corner (50.6-52 us vs 50); **no sigma-delta, no band-search FSM in RTL** | **integer-N only, under register control** (section 4); not autonomous |

The synthesizer must still be instanced and wired on die 1: without instances it cannot be characterized at all, and it is
the only LO that leaves REF_IN / AUX_CLK free for clocks.

## 1. Instances

| Instance | Master (netlist) | GDS / extraction | Outline um (published) | Supply domain |
|---|---|---|---|---|
| `lo_qvco` | `pt_lc_qvco5` (`lcvco/qvco5.spice`) | `generated/lcvco/pt_lc_qvco5.gds`; RC extraction `scratch/lo/r4_qvco2/rft6` | 848.0 x 627.9 | **VDD_LO (quiet rail, section 3)** |
| `lo_mmd` | `pt_lo_mmd` (`lo_mmd.spice`) | `generated/lo_mmd.{gds,ext.spice}` | 379.8 x 955.3 (ap4 staged: 379.9 x 383.3) | VDD_LOD |
| `lo_mmd_qdum` | `pt_lo_mmd_qdum` | `generated/lo_mmd_qdum.*` | 218.7 x 156.7 (ap4 staged: 100.0 x 194.7) | VDD_LOD |
| `lo_pfdcp` | `pt_lo_pfdcp` | `generated/lo_pfdcp.*` | 259.0 x 482.4 | VDD_LO |
| `lo_lf` | `pt_lo_lf` | `generated/lo_lf.*` | see `generated/lo_lf.gds` (0.194 mm2) | passive, VSS only |
| `lo_ext` | `pt_lo_ext` | `generated/lo_ext.*` | 324.1 x 481.9 | VDD_LOD |
| `lo_obs_i` | `pt_lo_obs` | `generated/lo_obs.*` | 202.3 x 86.5 (ap4 staged: 98.4 x 93.1) | VDD_LOD |
| `lo_obs_q` | `pt_lo_obs`, `EN` tied to VSS (Q-tank load; matched to `lo_obs_i` only while that is off too: with observation on, the I-side gates are in inversion and the Q-side ones are not, a few fF per node, i.e. of order 1 deg of quadrature by the 2.2 deg per 7.5 fF sensitivity) | same | same | VDD_LOD |

Literal port strings (connect by name; two of them have supplies or controls in unexpected positions):
```
pt_lc_qvco5     EN CMLSEL VTUNE IBIAS BAND0 BAND1 BAND2 BAND3 PRE IP IN QP QN VDD VDDB VSS ATB_EN ATB_VTUNE ATB_ITAIL
pt_lo_mmd       LP LN EN N0 N1 N2 N3 N4 N5 FB VDD VSS
pt_lo_mmd_qdum  LP LN EN QDP QDN VDD VSS
pt_lo_pfdcp     REF FB EN PRE IBIAS VTUNE VDD VSS ICP0 ICP1          (ICP0 ICP1 come AFTER VDD VSS)
pt_lo_lf        CP VT VSS
pt_lo_ext       EXT_IP EXT_IN EXT_QP EXT_QN LOI_IP LOI_IN LOI_QP LOI_QN EXT INT CMLSEL LO_IP LO_IN LO_QP LO_QN ATB_VB VDD VSS
pt_lo_obs       LP LN EN OBS VDD VSS
```

`pt_polyphase` is deleted (CP4-2, 2026-11-14); `LOI_*` belongs to the QVCO tank only.

## 2. Nets (connection intent)

Tank nets are 2.4 GHz, high impedance (tank Q 4-10): route each pair as a matched, shielded pair, Metal4/5, as short as
the floorplan allows; every fF of mismatch between the I pair and the Q pair is quadrature error (7.5 fF gave 2.2 deg).

| Net | Driver | Loads | Notes |
|---|---|---|---|
| `LOI_IP`, `LOI_IN` (I tank) | `lo_qvco.IP/IN` | `lo_ext.LOI_IP/LOI_IN`, `lo_mmd.LP/LN`, `lo_obs_i.LP/LN` | DC-coupled, ~1.7 V +- 0.4..0.6 V |
| `LOI_QP`, `LOI_QN` (Q tank) | `lo_qvco.QP/QN` | `lo_ext.LOI_QP/LOI_QN`, `lo_mmd_qdum.LP/LN`, `lo_obs_q.LP/LN` | same loads as the I tank by construction |
| `LO_IP/IN/QP/QN` | `lo_ext.LO_*` | `rxmix_i.lo_p/n`, `rxmix_q.lo_p/n`, `txmix_i.lo_p/n`, `txmix_q.lo_p/n` | biased by lo_ext to VB = 0.739 VDD; clamped to VSS when lo_ext is off |
| `REF_IN_P/N` pad pair | board | `lo_ext.EXT_IP/EXT_IN` **and** `rx_ref_in.INP/INN` (a `pt_diff_clk_rx`, section 5) | LO (ext modes) or reference clock, never both |
| `AUX_CLK_P/N` pad pair | board | `lo_ext.EXT_QP/EXT_QN` and `rx_aux_clk.INP/INN` | same |
| `lo_fb` | `lo_mmd.FB` | `lo_pfdcp.FB`; also a frequency-counter input of the digital macro (`fc_src`), <= 78 MHz | CMOS, 50 MHz nominal, **a 2.8-3.5 ns high pulse once per period, not a 50 % clock**: the counter input path must pass a 2.8 ns pulse |
| `lo_ref` | `rx_ref_in.OUTN` (= `ref_clk`) | `lo_pfdcp.REF` | 50 MHz XO on REF_IN in on-chip-LO mode |
| `lo_cp` | `lo_pfdcp.VTUNE` | `lo_lf.CP` | charge-pump node; guard, keep away from switching nets |
| `lo_vtune` | `lo_lf.VT` | `lo_qvco.VTUNE` | after the R3/C3 pole; shield; leakage here is static phase offset |
| `lo_obs` | `lo_obs_i.OBS` | `clk_obs16` input (rf_lo source) | LO/8, 300-310 MHz, drives ~2 pF / 2 mm. `lo_obs_q.OBS`: leave open |
| `lo_qvco.PRE` | QVCO (output, CMOS on `VDDB`) | none on die 1 | **Output. Not the same signal as `lo_pfdcp.PRE` (an input). Do not join them.** Leave unloaded (<= 30 fF) |
| `lo_mmd_qdum.QDP/QDN` | dummy prescaler output | none | leave open |
| `lo_qvco.ATB_VTUNE`, `ATB_ITAIL` | QVCO | analog test bus leaves | `ATB_ITAIL` **sinks** a 1/64 tail replica (~190 uA) when `ATB_EN = 1`: the ATB side must source it |

## 3. Supplies and bias

| Pin | Connect to | Demand |
|---|---|---|
| `lo_qvco.VDD` | **VDD_LO**, a dedicated quiet rail (own regulator output or own pad + on-die RC), star-connected, own decap | 22-25 mA; **noise <= 7 nV/rtHz from 100 kHz to 1 MHz** (pushing -60 MHz/V, risk LO-11; this is a requirement, not a preference); >= 200 pF local decap is not enough on its own, the density limit needs a regulator or an RC with corner <= 10 kHz |
| `lo_pfdcp.VDD` | VDD_LO (same quiet rail, after its own 10 ohm / decap branch) | supply current not measured in any bench (bias 10 uA x10 mirrors, 100 uA pump, OTA, PFD logic at 50 MHz: order 1 mA, an estimate); CP supply noise goes straight to VTUNE |
| `lo_qvco.VDDB` | VDD_LOD | PRE buffer supply, a few mA of 2.4 GHz CMOS current: keep it off VDD_LO |
| `lo_mmd.VDD`, `lo_mmd_qdum.VDD`, `lo_ext.VDD`, `lo_obs_*.VDD` | **VDD_LOD** (switched RF/PLL island rail) | lo_mmd 18-34 mA (ss..ff, extracted), lo_ext 11.8 mA (internal mode, tt, extracted), lo_obs **5.8-8.0 mA when enabled and dividing** (extracted, ss..ff; the published cell does not divide at ss / 3.15 V, 4 of 24 in-window corner cases, an open failure of the published `pt_lo_obs`); lo_mmd_qdum not measured (two 2.6 mA prescaler latches + two followers by design, ~8 mA estimate) |
| all `VSS` | analog ground; QVCO and CP returns star-connected to the VDD_LO decap | - |
| `lo_qvco.IBIAS` | one `core_bias` PLL-bank output, 10 uA **sourced into** the pin (NMOS diode `XNB` 1.44/1 to VSS) | the bank output must be **enabled with the QVCO** (today `lc_vco_reserved` has EN tied to VSS in `integration/core_bias.py:123`: that is the bug in MW-7) |
| `lo_pfdcp.IBIAS` | one more `core_bias` output, 10 uA sourced into an NMOS diode (`XB1` 20/32) | no output exists today (MW-30). The PLL bank has four outputs and five possible consumers (tx ring, cdr ring, a host_follow ring if one is kept, QVCO, lo_pfdcp). **The bank needs a fifth output, or QVCO and lo_pfdcp share nothing and the host ring's output is reused only if X1 (pll_host deleted, host_follow on `pll_cdr`) stands.** This file does not decide which ring is host_follow; bias/assembly must (`core_bias.py:17` still lists `pll_ring_host`) |
| `lo_mmd`, `lo_mmd_qdum`, `lo_obs`, `lo_ext` | no bias pin | self-biased from their VDD (resistor references) |

Total with the on-chip LO running: VDD_LO about 23-26 mA, VDD_LOD about 43-67 mA (sums of the rows above, including the two estimates; 66-93 mA in all). The power budget has no line for this yet.

If VDD_LO becomes a regulated 2.55-2.75 V rail (interface row LO22), the tank common mode drops from ~1.7 V and **every tank-connected cell (lo_ext INT pair, lo_mmd, lo_mmd_qdum, lo_obs) and the CP window / preset must be re-verified at that level**; they have only been verified at 1.7 V.

## 4. Controls (all active high, **0 = reset = safe/off**)

| Pin(s) | Function | Register field needed | Reset |
|---|---|---|---|
| `lo_ext.EXT`, `.INT`, `.CMLSEL` | LO mode, section 4.1 | `rfpll.config.lo_mode[1:0]` | 0 = off |
| `lo_qvco.CMLSEL` | PMOS header of both cores off (tank passive) | same net as `lo_ext.CMLSEL` | 0 |
| `lo_qvco.EN` | tail bias on. **EN-to-ready 1.5 ms** (bias filter) | `rfpll.state` (active) and `lo_mode == internal` | 0 |
| `lo_qvco.BAND[3:0]` | tank band, 15 = lowest frequency | `rfpll.config.vco_coarse[3:0]` | 0 |
| `lo_mmd.EN` | divider on | with `lo_qvco.EN` | 0 |
| `lo_mmd.N[5:0]` | VCO/FB = 2 x N, N = 16..63. **Codes 0..15 alias to 16..31** (N4 is ignored while N5 = 0), so code 0 divides by 32; the validator and any sigma-delta saturation must use the same rule | `rfpll.config.lo_n[5:0]`; later the sigma-delta output | 0 (divider off anyway) |
| `lo_mmd_qdum.EN` | same net as `lo_mmd.EN` | - | 0 |
| `lo_pfdcp.EN` | PFD/CP on | with `lo_qvco.EN` | 0 |
| `lo_pfdcp.PRE` (input) | 1 = PFD held in reset, VTUNE forced to the preset voltage | `rfpll.config.lo_preset` | 0 |
| `lo_pfdcp.ICP[1:0]` | Icp = 25 uA x (1 + ICP0 + 2 x ICP1) | `rfpll.config.lo_icp[1:0]` (LO18) | 0 = 25 uA. **Not a usable operating value with the published preset:** software must write 3 before releasing the preset (section 4.2) |
| `lo_obs_i.EN` | LO/8 observation on | `debug.clk_obs` source = rf_lo | 0 |
| `lo_qvco.ATB_EN` | connects `ATB_VTUNE`, `ATB_ITAIL` to the analog test bus | ATB code (LO17) | 0 |
| `lo_ext.ATB_VB` | LO common-mode sense / force | ATB code | high-Z |

### 4.1 `pt_lo_ext` mode pins (MW-1)

| `lo_mode` | EXT | INT | CMLSEL | Meaning | Also required |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | **off (reset)**: bias dividers off, LO nodes clamped to VSS, mixers off, each pad sees one NMOS drain | - |
| 1 | 1 | 0 | 0 | passive external LO (backup) | QVCO EN = 0; `rx_ref_in.EN = rx_aux_clk.EN = 0` |
| 2 | 0 | 1 | 0 | on-chip LO: CML driver on the QVCO tank | QVCO EN = 1 |
| 3 | 1 | 1 | 1 | **external LO through the CML driver (die-1 baseline)** | QVCO EN = 0 (its CMLSEL header off); `rx_ref_in.EN = rx_aux_clk.EN = 0` |

Decode: `EXT = (m==1)|(m==3)`, `INT = (m==2)|(m==3)`, `CMLSEL = (m==3)`. The 2-bit field cannot produce the four other pin
combinations (EXT INT CMLSEL = 110, 001, 011, 101). By inspection none is destructive (pad current <= 0.2 mA through the
10 k pad bias when EXT = 1; the CML tails are steered, not paralleled). 001 burns ~165 uA in the VLI divider with everything
else off; 101 leaves the LO nodes at VB with no drive (mixers half on); 011 may well work as an external-CML mode with the
pad switch off. **None of the four has been simulated**, which is why the field is an enum and not three bits.

Known weakness, not simulated (review A6): with `CMLSEL = 0` (modes 0, 1, 2) both ends of the VLI divider are off, so the
gates of the EXT pair float while the 2 pF MIM couples the pad signal onto them. A pull-down on VLI for `CMLSEL = 0` is
the fix; it goes with the next `lo_ext` netlist change (MW-20).
Change `lo_mode` only with the mixers disabled, and wait **>= 20 us** before enabling them (VB and the LO DC level settle
through 20 k / 3 pF branches; the extracted benches use 100 ns only because they start from a precharged state).
The board must not DC-drive REF_IN / AUX_CLK while EXT = 1.
Pad load from `pt_lo_ext` in every mode, per pad: the 6 V series-switch drain, a 2 pF MIM into a 2 k node with two junction
clamps, and a 200 fF bootstrap MIM (budget this for the REF_IN reference clock in mode 2 as well).

### 4.2 Bring-up sequence for the on-chip LO without FSM or sigma-delta (integer-N)

1. `lo_mode = 2`, `lo_preset = 1`, **`lo_icp = 3` (100 uA)**, `lo_n = N`, `vco_coarse = band`, enables on. Wait 1.5 ms.
2. Band search by software: for each band read the frequency counter on `lo_fb` (= f_VCO / 2N) against `ref_clk`; pick the band whose count is closest to f_ref with VTUNE at the preset.
3. `lo_preset = 0`. The loop acquires.

**What lock time to expect is not qualified at transistor level for the published cells.** The published `pt_lo_pfdcp`
presets VTUNE to VDD/2 (two 40 k resistors, `lo_pfdcp.spice:135-138`), not to the 2.1 V that LO20 and the whole lock ladder
assume, so the loop locks in the low-Kvco half (25-40 MHz/V). Behavioural model on the published filter (reviewer's run,
`scratch/lo-ap4/review/lock/lowkv.json`): Icp 100 uA: fc 88-135 kHz, PM 65-67 deg, lock 32-35 us; **Icp 25 uA (the reset
code): fc 29-41 kHz, PM 44-52 deg, lock 88-130 us**. Interface row LO25 tracks the preset change.

Channel plan in integer-N: f_LO = 2 N f_ref, so 100 MHz steps at 50 MHz; any channel is reachable by moving the board
reference (N = 24, f_ref = 50.0-51.74 MHz covers 2.400-2.4835 GHz). Fractional-N needs the sigma-delta on `lo_mmd.N[5:0]`
(RTL does not exist; enable it only after lock, LO20).

## 5. Clock selects and the reference clock (MW-2, MW-19)

* **Decode lives in the digital macro** (standard cells, static, combinational, reset to all-zero), not in an analog glue
  cell: the analog cells take one-hot static levels and there is no analog reason to decode next to them. The table is
  `README.md` "Register-map glue"; the missing fields are the ring-PLL reference `PS_{REF,AUX,H2D}`, the ring modulus
  `N4/N8` per ring, `lo_mode` (above), `EN` of each `pt_diff_clk_rx` (`SE` has no effect in the published
  `diff_clk_rx.spice`, so no field is needed for it), and `EN` of each `pt_prescale` and of `pt_wordclk`. One-hot means at most one 1; all-zero
  = stopped; software switches through stopped (write 0, wait >= 1 us, write the new code).
* **`ref_clk` driver:** instance `rx_ref_in`, a `pt_diff_clk_rx` on the REF_IN pad pair
  (`INP INN EN SE OUTP OUTN PRESENT ATB_DET VDD VSS`; same rail as the existing `rx_aux_clk` instance, whatever
  assembly uses for it: the README says the island rail, an earlier note says always-on, and the receiver itself does
  not care). With `EN = 0` `OUTN` is static high, so `ref_clk` is stuck at 1 in LO modes 1 and 3. `OUTN` -> net `ref_clk`
  -> `clockmux.REF`, the digital macro `ref_clk`, `lo_pfdcp.REF`; `PRESENT` -> `ref_present`. `EN` = 1 except in LO
  modes 1 and 3 (REF_IN then carries the 2.4 GHz LO). The ring PLLs take their reference from `clockmux.PREF`, not from
  `ref_clk` directly (`netlist.py:113` binds `pll_cdr.REF -> ref_clk`: stale).
* **`clockmux.H2D`** needs the H2D_CLK pad receiver output as a port of `pt_analog_physical` (today it reaches only the
  macro). With an external LO this is the only clock the chip has: PREF = H2D -> ring (N4) -> prescale -> `HF` ->
  `CONV_CLK` / `HOST_CLK`.
* **Host clock with no PLL (SPI-only bring-up):** today `HOST_CLK` can only come from a locked ring (`HS_INT`, `HS_HF`),
  so a dead ring means no host link. `XMH` in `clockmux.spice` has two unused mux inputs tied to VSS. Proposal CM-1
  (interface-changes): wire them to `H2D` and `REF` with selects `HS_H2D`, `HS_REF`, so the FPGA-forwarded clock or the
  board reference can clock the host link directly. Two new ports, one cell re-layout; **not built** (needs the
  coordinator's yes because the port list changes).
* One `pt_prescale` instance exists but `CONV_INT`, `HOST_INT` and `HF` are three differently divided clocks: three
  instances are needed (ring -> CONV_INT, ring -> HOST_INT, host_follow ring -> HF), each with its own one-hot `D2..D16`.
* `pt_wordclk` `D10/D20` decode from `cfg_bits_per_cycle` as in the README table.

## 6. LO drive at the mixers (MW-20)

The published `pt_lo_ext` (same CML driver in internal and external-CML mode) gives the extracted RX mixers 3.3 dB less
conversion gain than the ideal square LO of the rf_rx benches at tt, 1.9 dB less at ff and 9.8-11.6 dB less at
ss/32/3.15 (joint extracted bench, internal mode, in band; `README.md` round 6, interface row MW-20a). External modes were
not run with the mixers. For die 1: route `lo_ext.ATB_VB` to the analog test bus so the LO common mode can be forced
(per-die trim; at ss 2.45 V recovers the loss to 3.4 dB). A revised `pt_lo_ext` is staged but not qualified; its port list
is unchanged, its outline is not (345.1 x 387.2 um staged against 324.1 x 481.9 um published).
