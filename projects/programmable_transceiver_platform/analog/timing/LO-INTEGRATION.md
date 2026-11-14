# LO subsystem: pin list and connection intent for chip-top integration

Pin orders are the `.subckt` lines of the named netlists; if a netlist and this file disagree, the netlist wins.
The bindings below are the ones in `integration/top/pt_chip.conn`; control decode is
`integration/top/ctl_ports.txt`. Block results and open items: [`README.md`](README.md).

## 0. Status

| Path | State | Use |
|---|---|---|
| External LO through the CML driver (`lo_mode` 3), I on REF_IN, Q on AUX_CLK | published; 1.0-4.5 Vpp per leg on the level criterion; not benched with the mixers | RF baseline when the synthesizer does not work, with reduced RX gain (section 6) |
| External LO, passive path (`lo_mode` 1) | published; fails ss at 4.5 Vpp | backup |
| On-chip synthesizer (`lo_mode` 2) | every cell published and instanced; no QVCO regulator; no fractional-N modulator or band-search state machine in RTL | integer-N under register control (section 4.2); not qualified as a loop |

There is no polyphase network; `LOI_*` belongs to the QVCO tank only.

## 1. Instances

| Instance | Master (netlist) | Published files | Outline um (GDS) | Island |
|---|---|---|---|---|
| `qvco` | `pt_lc_qvco5` (`lcvco/qvco5.spice`) | `generated/lcvco/pt_lc_qvco5.gds` | 898.0 x 652.9, fill keep-out halo included | lo, on `VDD_LO` |
| `lo_mmd` | `pt_lo_mmd` (`lo_mmd.spice`) | `generated/lo_mmd.*` | 377.8 x 955.8 | lod |
| `lo_mmd_qdum` | `pt_lo_mmd_qdum` | `generated/lo_mmd_qdum.*` | 216.7 x 157.2 | lod |
| `lo_pfdcp` | `pt_lo_pfdcp` | `generated/lo_pfdcp.*` | 257.0 x 482.9 | lo, on `VDD_LO` |
| `lo_lf` | `pt_lo_lf` | `generated/lo_lf.*` | 402.8 x 482.0 | lo (passive, VSS only) |
| `lo_ext` | `pt_lo_ext` | `generated/lo_ext.*` | 322.1 x 482.4 | lod |
| `lo_obs` | `pt_lo_obs` | `generated/lo_obs.*` | 200.3 x 87.0 | lod |
| `lo_obs_q` | `pt_lo_obs`, `EN` tied to VSS (matched Q-tank load) | same | same | lod |
| `lo_vreg` | `pt_lo_vreg` | none (build demand) | - | lo |

The lo and lod islands belong to the rf enable group (`island_on[1]`), not to the pll group.

Port strings (connect by name):
```
pt_lc_qvco5     EN CMLSEL VTUNE IBIAS BAND0 BAND1 BAND2 BAND3 PRE IP IN QP QN VDD VDDB VSS ATB_EN ATB_VTUNE ATB_ITAIL
pt_lo_mmd       LP LN EN N0 N1 N2 N3 N4 N5 FB VDD VSS
pt_lo_mmd_qdum  LP LN EN QDP QDN VDD VSS
pt_lo_pfdcp     REF FB EN PRE IBIAS VTUNE VDD VSS ICP0 ICP1          (ICP0 ICP1 come AFTER VDD VSS)
pt_lo_lf        CP VT VSS
pt_lo_ext       EXT_IP EXT_IN EXT_QP EXT_QN LOI_IP LOI_IN LOI_QP LOI_QN EXT INT CMLSEL LO_IP LO_IN LO_QP LO_QN ATB_VB VDD VSS
pt_lo_obs       LP LN EN OBS VDD VSS
```

## 2. Nets (connection intent)

Tank nets are 2.4 GHz and high impedance: route each pair as a matched, shielded pair on Metal4 / Metal5, as
short as the floorplan allows. Wiring mismatch between the I pair and the Q pair is quadrature error.

| Net | Driver | Loads | Notes |
|---|---|---|---|
| `LOI_IP`, `LOI_IN` (I tank) | `qvco.IP/IN` | `lo_ext.LOI_IP/LOI_IN`, `lo_mmd.LP/LN`, `lo_obs.LP/LN` | DC-coupled |
| `LOI_QP`, `LOI_QN` (Q tank) | `qvco.QP/QN` | `lo_ext.LOI_QP/LOI_QN`, `lo_mmd_qdum.LP/LN`, `lo_obs_q.LP/LN` | same kinds of load as the I tank |
| `LO_IP/IN/QP/QN` | `lo_ext.LO_*` | RX and TX mixer LO gates | biased by `lo_ext`; clamped to VSS when `lo_ext` is off; no isolation cell (lod and the mixers are in one enable group) |
| `REF_IN`, `REF_IN_N` pads | board | `lo_ext.EXT_IP/EXT_IN` and `rx_ref_in.INP/INN` | external LO (I) or reference clock, never both |
| `AUX_CLK_P`, `AUX_CLK_N` pads | board | `lo_ext.EXT_QP/EXT_QN` and `rx_aux_clk.INP/INN` | external LO (Q), auxiliary clock or forwarded wire clock: one use at a time |
| `LO_FB` | `lo_mmd.FB` | `lo_pfdcp.FB`; frequency-counter input of the digital macro | CMOS at f_ref, a narrow high pulse once per period, not a 50 % clock |
| `ref_clk` | `rx_ref_in.OUTN` | `lo_pfdcp.REF`, `clockmux.REF`, digital macro | board reference on REF_IN in on-chip-LO mode |
| `LO_CP` | `lo_pfdcp.VTUNE` | `lo_lf.CP` | charge-pump node; guard, keep away from switching nets |
| `LO_VTUNE` | `lo_lf.VT` | `qvco.VTUNE` | shield; leakage here is static phase offset |
| `LO_OBS` | `lo_obs.OBS` | `clk_obs16.IN1` through an isolation clamp | LO/8; `lo_obs_q.OBS` is left open |
| `qvco.PRE` | QVCO (output, on `VDDB`) | none | **Output. Not the same signal as `lo_pfdcp.PRE` (an input). Do not join them.** Left open |
| `lo_mmd_qdum.QDP/QDN` | dummy prescaler | none | left open |
| `qvco.ATB_VTUNE`, `ATB_ITAIL` | QVCO | not bound to a test-bus leaf | `ATB_ITAIL` sinks a 1/64 tail replica when `ATB_EN` = 1: a test-bus leaf must source it |
| `lo_ext.ATB_VB` | `lo_ext` | test-bus leaf `ATBN_quadrature_bias` | LO common mode, sense or force (section 6) |

## 3. Supplies and bias

| Pin | Connect to | Demand |
|---|---|---|
| `qvco.VDD` | `VDD_LO`, the output of `lo_vreg` on the lo island; star-connected, own decap | 22-25 mA (extracted, `scratch/lo/r5_pn/ext12.json`). Each supply-borne tone <= -60 dBc and <= 0.2 ps rms in total; noise <= 7 nV/rtHz from 100 kHz to 1 MHz (pushing -60 MHz/V, risk LO-11) |
| `lo_pfdcp.VDD` | `VDD_LO` | order 1 mA, not measured; charge-pump supply noise goes straight to VTUNE |
| `qvco.VDDB` | `RAIL_lod` | PRE buffer supply, a few mA of 2.4 GHz CMOS current, not measured: keep it off `VDD_LO` |
| `lo_mmd.VDD`, `lo_mmd_qdum.VDD`, `lo_ext.VDD`, `lo_obs*.VDD` | `RAIL_lod` | `lo_mmd` 17-35 mA (ss to ff, extracted); `lo_ext` 11.1 mA at tt in internal mode (extracted); `lo_mmd_qdum` ~8 mA by design (two 2.6 mA latches + followers), not measured; `lo_obs` 5.8-8.0 mA when enabled and dividing (extracted, `scratch/timing/lo_obs/results.json`) |
| all `VSS` | analog ground; QVCO and charge-pump returns star-connected to the `VDD_LO` decap | - |
| `qvco.IBIAS` | `BIAS_qvco` (core_bias output enabled by `c_qvco_en`) | 10 uA sourced into the pin |
| `lo_pfdcp.IBIAS` | `BIAS_lo_pfdcp` (enabled by `c_lo_pfdcp_en`) | 10 uA sourced into the pin |
| `lo_mmd`, `lo_mmd_qdum`, `lo_obs`, `lo_ext` | no bias pin | self-biased from their VDD |

The tank-connected cells (`lo_ext` INT pair, `lo_mmd`, `lo_mmd_qdum`, `lo_obs`) and the charge-pump window are
verified at a tank common mode of about 1.7 V (QVCO on the die supply). A regulated `VDD_LO` lowers it; they
must be re-verified at that level.

## 4. Controls (all active high, **0 = reset = safe/off**)

| Pin(s) | Function | Macro port | Register field |
|---|---|---|---|
| `lo_ext.EXT`, `.INT`, `.CMLSEL` | LO mode, section 4.1 | `c_lo_ext`, `c_lo_int`, `c_lo_cmlsel` | `rfpll.config.lo_mode[1:0]` |
| `qvco.CMLSEL` | PMOS header of both cores off (tank passive) | `c_lo_cmlsel` (same net) | same |
| `qvco.EN` | tail bias on; **1.5 ms from EN to ready** | `c_qvco_en` = (`rfpll.state` active) and (`lo_mode` = 2) and `island_on[1]` | `rfpll.state`, `lo_mode` |
| `qvco.BAND[3:0]` | tank band, 15 = lowest frequency | `c_qvco_band[3:0]` | `rfpll.config.vco_coarse` |
| `lo_mmd.EN`, `lo_mmd_qdum.EN` | divider and its dummy on | `c_lo_mmd_en` (= `c_qvco_en`) | - |
| `lo_mmd.N[5:0]` | VCO/FB = 2 x N, N = 16..63. Codes 0..15 alias to 16..31 (N4 is ignored while N5 = 0) | `c_lo_mmd_n[5:0]` | `rfpll.config.lo_n` |
| `lo_pfdcp.EN` | PFD and charge pump on | `c_lo_pfdcp_en` (= `c_qvco_en`) | - |
| `lo_pfdcp.PRE` (input) | 1 = PFD held in reset, VTUNE forced to the preset voltage (VDD/2) | `c_lo_pre` | `rfpll.config.lo_preset` |
| `lo_pfdcp.ICP[1:0]` | Icp = 25 uA x (1 + ICP0 + 2 x ICP1); reset = 25 uA | `c_lo_icp[1:0]` | `rfpll.config.lo_icp` |
| `lo_vreg.EN` | quiet-rail regulator on | `c_lo_vreg_en` = `c_qvco_en` or `c_lo_pfdcp_en` | - |
| `lo_obs.EN` | LO/8 observation on | `c_lo_obs_en` | `debug.clk_obs.source` = rf_lo |
| `qvco.ATB_EN` | connects `ATB_VTUNE`, `ATB_ITAIL` | `c_qvco_atb_en` | `rfpll.config.atb_enable` |

All LO enables are gated with the rf island group (`island_on[1]`).

### 4.1 `pt_lo_ext` mode pins

| `lo_mode` | EXT | INT | CMLSEL | Meaning | Also required |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | **off (reset)**: LO nodes clamped to VSS, mixers off | - |
| 1 | 1 | 0 | 0 | passive external LO (backup) | QVCO off; `rx_ref_in.EN` = `rx_aux_clk.EN` = 0 |
| 2 | 0 | 1 | 0 | on-chip LO: CML driver on the QVCO tank | QVCO on |
| 3 | 1 | 1 | 1 | external LO through the CML driver | QVCO off (its `CMLSEL` header off); `rx_ref_in.EN` = `rx_aux_clk.EN` = 0 |

Decode: `EXT = (m==1)|(m==3)`, `INT = (m==2)|(m==3)`, `CMLSEL = (m==3)`. The field is an enum because the four
other pin combinations have not been simulated.

* Change `lo_mode` only with the mixers disabled and wait >= 20 us before enabling them (the LO bias settles
  through 20 k / 3 pF branches).
* The board must not DC-drive REF_IN / AUX_CLK while `EXT` = 1.
* In modes 1 and 3 REF_IN carries the LO, so `ref_clk` is static and `rx_ref_in` is disabled by the decode.
  The forwarded wire clock and the external LO both use the AUX_CLK pair and exclude each other.
* `pt_lo_ext` loads each of the four pads in every mode (series-switch drain, a 2 pF coupling capacitor into a
  2 k node, a 200 fF bootstrap capacitor): budget it for the reference clock in mode 2 as well.
* `pt_lo_ext` has no I/Q phase trim.

### 4.2 Bring-up sequence for the on-chip LO (integer-N, software band search)

1. `lo_mode` = 2, `lo_preset` = 1, **`lo_icp` = 3 (100 uA)**, `lo_n` = N, `vco_coarse` = band, enables on.
   Wait 1.5 ms.
2. For each band read the frequency counter on `LO_FB` (= f_VCO / 2N) against `ref_clk`; pick the band whose
   count is closest to f_ref with VTUNE at the preset.
3. `lo_preset` = 0. The loop acquires.

The reset value of `lo_icp` (25 uA) is not a usable operating value. Channel plan: f_LO = 2 N f_ref; with
N = 24 a board reference of 50.0-51.74 MHz covers 2.400-2.4835 GHz.

## 5. Clock selects and the reference clock

* The decode of every clock select lives in the digital macro (`README.md` "Register-map glue").
* `ref_clk`: instance `rx_ref_in`, a `pt_diff_clk_rx` on the REF_IN pad pair, on the always-on core rail;
  `OUTN` -> `ref_clk`, `PRESENT` -> `s_ref_present`. With `EN` = 0 `OUTN` is static.
* `rx_aux_clk`: a `pt_diff_clk_rx` on the AUX_CLK pad pair, on the debug island; `OUTP` -> `AUX_CK`, clamped onto
  the pll island as `AUX_CK_P`, which feeds `clockmux.AUX`, `clockmux.WCK` and `cdr.WCK_IN`. `WS_AUX` and
  `WS_WCK` therefore select the same clock.
* Both pad pairs use `pad_refpad`; their `VCM` is `pt_refvcm` (`c_refvcm_en`).
* The ring PLLs take their reference from `clockmux.PREF`, not from `ref_clk` directly.
* `clockmux.H2D` is the H2D_CLK pad receiver output. With an external LO this is the only clock the chip has:
  `PREF` = H2D -> CDR ring (N4) -> `prescale_hf` -> `HF` -> `CONV_CLK` / `HOST_CLK`.
* Three `pt_prescale` instances: `prescale` (line ring -> `HOST_INT`), `prescale_conv` (line ring -> `CONV_INT`),
  `prescale_hf` (CDR ring -> `HF`), each with its own enable and one-hot `D2..D16`.

## 6. LO drive at the mixers

The published `pt_lo_ext` gives the extracted RX mixers 3.3 dB less conversion gain than an ideal square LO at
tt, 1.9 dB less at ff and 9.8 dB less at ss/32/3.15 (11.6 dB with a 0.40 V tank); table and source in
`README.md` "RF LO". Forcing `ATB_VB` to 2.45 V through the test bus recovers the ss loss to 3.4 dB, so the
`ATBN_quadrature_bias` leaf must be reachable as a per-die trim.

## 7. Placement constraints

The QVCO runs at the RF carrier, so the PA can pull it and its position is constrained (interface rows
INT23-2, -3, -8, -13).

| Rule | Value |
|---|---|
| QVCO spiral centres to the west die edge | >= 1.7 mm |
| QVCO spiral centres along the west edge from the RF_TX and the RF_RX pad pairs | >= 1.0 mm; no spiral axis toward the RF pads |
| QVCO to the digital macro | >= 800 um with a continuous substrate-tie region between them |
| QVCO to the ring PLLs and `rfdriver` | >= 500 um |
| QVCO to the LNA | >= 250 um |
| `lo_mmd` to the bandgap core of `core_bias` | >= 300 um |
| Forwarded-clock route from `rx_aux_clk` to spirals and tank nets | >= 300 um; shielded differential pair taken from the receiver output, never from the pad net |
| Other cells to the outer-turn metal of a spiral | >= 25 um, nothing over a spiral or its feeds, no ring around a spiral. The published QVCO outline already contains this halo and its fill keep-out markers |
| VTUNE filter capacitor C3 | at the QVCO, not at `lo_lf` (not implemented: C3 is inside `pt_lo_lf`) |

These conflict with the need for short tank nets (`lo_ext` and `lo_mmd` next to the QVCO tank ports, LO short to
the mixers at the west edge); the floorplan has to resolve it.

## Open items

* No floorplan honours section 7 yet; `lo_obs_q`, `rx_ref_in` and five of the six `obs_pre4` are not in the last
  floorplan.
* `VDD_LO` state in `lo_mode` 1 and 3: the regulator is off while `lo_ext` biases the tank nodes (top decision
  D-LOVREG). `pt_lo_vreg` is not published.
* `integration/core_bias.py` still names the QVCO bias output `lc_vco_reserved` and has no `lo_pfdcp` output;
  `pt_chip.conn` binds `BIAS_qvco` and `BIAS_lo_pfdcp`.
* External-LO leakage through the bond wires into RF_RX (interface row INT23-1) and the minimum external drive
  in `lo_mode` 3 are open.
* AUX_CLK as the forwarded wire clock: receiver bench (25-810 MHz with the 3.1 mm route), the register rule that
  makes external-LO and wire-clock use exclusive, and the debug-island dependency are open (top decision
  D-AUXWCK).
