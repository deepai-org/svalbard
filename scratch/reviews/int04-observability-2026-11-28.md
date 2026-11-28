# INT-04: minimum bring-up observability, per chip (2026-11-28)

This was a read-only check. Nothing was rerun and no design file or register row was edited. It answers one question for each chip: on the design as it will tape out, what can a person at the bench see using only SPI, the host pads, CLK_OBS / DBG_OBS, ATB0/1 and the frequency counters? The answer must be enough to tell a half-working die from a dead one and to choose the per-chip supply trim.

Sources (floorplan tree `/home/ubuntu/svalbard-fp`, branch fp-plan-code @ 95bb1a17, the KH_CONN=1 state):
- `integration/chips/{common.conn, rf/chip.conn, wired/chip.conn, ctl_ports.txt}`
- `rtl/pt_regfile.sv` (the ATB switch decode and its island gating) and `rtl/pt_digital_macro.sv`
- `spec/{observation.md, register-map.md, chips.json}`
- the delivered macro netlists `scratch/digital-macro-baseline/{rf,wired}/pt_digital_macro.pnl.v` (main tree)

Legend: **P** = present and bound at the top. **P-proxy** = only an indirect indicator. **U** = in the spec or as a block pin, but not bound at the top. **M** = missing.

## Preconditions that apply to every item

- Frequency counters (0xE8/0xEA) count against `ref_clk`, so **REF_IN must have a clock** on the board.
- CLK_OBS needs the debug island on.
- ATB leaves on island nodes close only when that island is on and power-good (`pt_regfile.sv` 1319-1364).
- The bandgap interlock counts SCLK (PWR-14). Bring-up software must clock ≥ 256 SCLK after `bgap_ena`, or the chip looks dead. `bandgap_ok` (DBG_OBS 12) is this digital timer, not an analog comparator. VBG on ATB 55 is the only real bandgap reading.
- Layout dependency (INT-13, not observability): pt_wired fpw-8 / fpw-11 layout smoke still shows the POR_BYPASS PD/PU ties floating (commit 4cb46fe6). Until that lands, the "digital alive" path is not proven on the assembled GDS.

## Per-chip table

| # | Minimum item | pt_rf | pt_wired |
|---|---|---|---|
| 1 | Digital alive: SPI read-back | **P**. ID 0x5356 @0x00, ABI/hash 0x08/0x09, chip id 0xFE (=1), RESET_STATUS 0x0D. Any R/W field (e.g. 0x4A) works as scratch. DBG_OBS 3 commit toggle, 36 rst_n. Works with every PLL stopped (SCLK only). | **P**. Same; chip id 2. |
| 2 | Each island supply on/off | **P** for rf_rx, pll, conv, debug: ATB1 8/9/11/12 plus `status.health.switch_pg` b0..b9 (0xFF), ISLAND_STATUS 0x0A, DBG_OBS 5/6/8/9. **P-proxy** for rf_tx, rf_tx_b, lod, lo: PG bit only, no rail voltage. **U** for the regulator outputs: `lo_vreg.ATB_OUT` (VDD_LO through 1 k) and `pll_vreg2.ATB_OUT` (VREG_TX through 20 k) are tied `~-` (rf conn l.203, common l.102). VREG_CDR has no tap at all. | **P** for wired_rx, wired_tx, pll, debug: ATB1 7/10/9/12 plus switch_pg b4/b6/b7/b9, and `isw_wired_tx_b` has its own PG. **P-proxy** for wired_cap: PG b5 only. **U** for VREG_TX: `pll_vreg2.ATB_OUT~-`. VREG_CDR has no tap. |
| 3 | Bandgap / bias / references on ATB | **P**. VBG 55, master ibias 1, VREF0 2, VCM 3, IDAC1 57, trunks TRK_RF_RX 14, TRK_PLL 29, TRK_CONV 35, TRK_DEBUG 56, VREF_CONV 36, REF_VCM 32, plus per-block biases 15-21/33/34/38/39/42. **U** for TRK_LO: `core_bias.TRK_LO~-` (l.90), and code 22 is in `atb_no_leaf` for pt_rf, so the hardened regfile rejects it. | **P**. VBG 55, 1/2/3/57, TRK_WIRED_RX 22, TRK_PLL 29, TRK_DEBUG 56, REF_VCM 32, CTLE 24, wiredtx 26, detect 28, HS 40, TERM_VCM 27, HS_VBIAS 23, wiredtx AVGP/AVGN 59/60. **U** for TRK_WIRED_TX: `core_bias.TRK_WIRED_TX~-` (l.87), and code 14 is rejected on pt_wired. **M** for slicer bias: code 25 is tied VSS (OBS-12). |
| 4 | Every ring/VCO/PLL countable, plus lock or a proxy | **P** for the TX ring (fc 1, CLK_OBS 8/9, lock DBG_OBS 10), the CDR ring (fc 2, CLK_OBS 14, lock DBG_OBS 48), ring_osc (fc 3), vco_replica (fc 4), aosc (fc 5, CLK_OBS 12) and dig_ring (fc 7). **P-proxy** for the LO: fc 6 = LO_FB (f_VCO/2N; count = f_ref means locked), CLK_OBS 1 = LO/8 (I tank), no lock bit. The runaway detector `lo_vtdet` is bound (`s_lo_vtdet=LO_VTDET`, placed) and gives `lo_vt_high` / `lo_vt_runaway` (DBG_OBS 53/54, rfpll.status). | **P** for the TX ring, CDR ring, ring_osc, vco_replica, aosc and dig_ring (fc 1/2/3/4/5/7, CLK_OBS 8/9/14/10/11/12, locks DBG_OBS 10/48, cdr_freq_ok / fll_lost 16/17/37/38). char_ro33/ro50/cmldiv are on CLK_OBS 15 only (FPGA counts them, no on-chip counter). fc 6 is tied VSS, which is correct (no LO). **M** for word clocks WRX/WTX_WCLK40: flag only (`rx_flags.wclk_alive`), and clk_obs IN0/1/4/7 are tied VSS (OBS-13). |
| 5 | Trim decision input: digital speed on the die | **P**. `pt_dig_ring` (41 mcu7t5v0 inversions on the core supply) is in the delivered macro netlist (`dring.*`, `dring_half` present). It is enabled by `debug.replica.dig_ring_enable` and counted as fc source 7 (edges/2). Needs REF_IN. ring_osc (fc 3) is a second, analog-rail speed reading. | **P**. Same: netlist carries `dring.*` / `dring_half`. char_ro33/ro50 on CLK_OBS 15 add 3.3 V / 5 V-cell speed. |
| 6 | pt_rf: LO VTUNE | **U**. `qvco.ATB_VTUNE~- ATB_ITAIL~-` (l.206). The block has the tap (20 k + TG, gated by `ATB_EN`) and `c_qvco_atb_en` is bound to `qvco.ATB_EN`, but no leaf. Railed high is caught by `lo_vt_high`. Railed low and wrong band cannot be told apart (OBS-7). | n/a |
| 6 | pt_wired: CDR / ring equivalents | n/a (CDR VCTRL is also unobserved on pt_rf) | TX ring VCTRL **P** (ATB1 30, `ATBN_pll_vctrl`). **U** for CDR ring VCTRL: `pll_cdr.ATB_VCTRL~CDR_VCTRL` exists as a net, but no leaf (OBS-5). **U** for VREG_TX / VREG_CDR (row 2). RX ring bias: no leaf. |

Verdict: **items 1, 3 (except the trunk), 4 and 5 are met on both chips.** On pt_rf, LO VTUNE and the LO / ring regulator outputs fail the minimum. On pt_wired, CDR VCTRL, the regulator output and the TX trunk fail it. Every failing node already exists as a block pin, and in each case only the top-level leaf is missing.

## Cheapest fixes under the freeze

There is a top-level-only route that needs no macro re-harden. I read the hardened regfile decode (`pt_regfile.sv` 1305-1373). Several ATB1 codes are **accepted on each chip, reach the global bus through their group bit, and today sense a dead or duplicate node**:

| Code | Switch / group | Gate | Node today | Usable on |
|---|---|---|---|---|
| 6 | sw[5], grp0 (LOCAL0) | none | VDD (duplicate of 5) | both |
| 41 | sw[40], grp2 (LOCAL2) | none | VSS (dead) | both |
| 25 | sw[24], grp2 (LOCAL2) | wired island | VSS (dead) | pt_wired only (the gate is never true on pt_rf) |
| 37 | sw[36], grp3 (LOCAL3) | conv island | VCM_MASTER (duplicate of 3) | pt_rf only (no conv island on pt_wired) |
| 4 | sw[3] | not in any group OR | VSS | **unusable** (never reaches ATB1_GLOBAL) |

Each of these leaves is already placed. The fix is to rebind the existing leaf's `NODE~` in the conn and route the new node to it. Moving the leaf closer is within the standing rulings.

| Fix | Chip | Change | Block change? |
|---|---|---|---|
| F1. LO VTUNE on ATB1 41 | rf | `qvco ATB_VTUNE~ATBN_lo_vtune`; `atb1_leaf41 NODE~ATBN_lo_vtune` (bring-up: set `rfpll.config.atb_enable`) | top-level only |
| F2. VDD_LO on ATB1 6 | rf | `lo_vreg ATB_OUT~ATBN_vdd_lo`; `atb1_leaf6 NODE~ATBN_vdd_lo` (1 k series, DC read) | top-level only |
| F3. VREG_TX on ATB1 37 | rf | `pll_vreg2 ATB_OUT~ATBN_vreg_tx`; `atb1_leaf37 NODE~ATBN_vreg_tx` (reading needs the conv island on; 20 k series) | top-level only |
| F4. CDR VCTRL on ATB1 41 | wired | `atb1_leaf41 NODE~CDR_VCTRL` (same structure as TX ring code 30) | top-level only |
| F5. VREG_TX on ATB1 6 | wired | `pll_vreg2 ATB_OUT~ATBN_vreg_tx`; `atb1_leaf6 NODE~ATBN_vreg_tx` | top-level only |
| F6. TRK_WIRED_TX on ATB1 25 | wired | `core_bias TRK_WIRED_TX~ATBN_wiredtx_trunk`; `atb1_leaf25 NODE~ATBN_wiredtx_trunk` (wired-gated, which is right for this node) | top-level only |
| F7. TRK_LO, CDR VCTRL on pt_rf, VREG_CDR, wired_cap rail, word clocks on CLK_OBS | rf / wired | Not enough free accepted codes or CLK_OBS inputs on pt_rf. Each needs either a regfile `atb_no_leaf` / decode change, or new iso cells on clk_obs IN | **block change (macro re-harden): ask**; post-tapeout list |

The rebinds, once approved, also need these follow-ups:
- `observation.md`, the register-map code table and the D-ATB entry in `decisions.md`: names change (code 6 is no longer "host VDD", 41 no longer "usbfs_vref", 25 no longer "slicer_bias", 37 no longer "conv_vcm").
- the gen_regfile conn-vs-`chips.json` check: the accepted set does not change, so it should stay green.
- check_conn / LVS by name on the next plan run.

Ruling needed: this repurposes codes that D-ATB deliberately tied to VSS, and it touches analog nodes, so it needs the coordinator. All of F1-F6 are top-level wiring only, with no macro pin or outline change. The triage ranks INT-04 as KILLER (debuggability), so it fits the freeze exception.

Ancillary findings:
- **CSP-01 is stale.** VCO replica VCTRL has code 58 with leaves on both buses on both chips (`common.conn` atb0_leaf58 / atb1_leaf58).
- The `ctl_ports.txt` note on `c_obs_pre4_en` ("sources 2,3,5,6,14 are on the regfile's forbidden list today (MW-29)") looks stale. `pt_regfile.sv` has no such reject: `o_debug_clk_obs__source` is gated only by `island_on[5]`.

## Top 3 missing items for telling half-working from dead

1. **pt_rf LO VTUNE (F1).** A QVCO that does not count on fc 6 might be railed low, in the wrong band, have a dead tail, or be unpowered, and none of these can be told apart. The tap and its enable already exist in the block; only the leaf is missing.
2. **Ring / LO regulator outputs (F2, F3, F5; VREG_CDR unfixable now).** If a ring or the QVCO does not run, the regulator could be dead, or the oscillator could be dead behind a good regulator. The supply trim also moves these outputs, so you cannot see whether 3.50 V helped the analog rails. Today only the upstream island rail and its PG are visible.
3. **pt_wired CDR VCTRL and TX trunk (F4, F6).** CDR lock and count exist. But a CDR that fails to lock cannot be classed as railed control, a dead VCO or no bias. The wired TX bank's trunk bias (several BLOCK-DEAD rows: WTX-08/09) is unreadable, so "TX dead" and "TX bias absent" look the same.
