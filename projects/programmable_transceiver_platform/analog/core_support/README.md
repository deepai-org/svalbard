# Core support: POR/reset, master bias and bias distribution

This directory imports two upstream cells and qualifies them, together with
our per-island bias distribution, against the **safe** and **clean** tests in
[`spec/tapeout-plan.md`](../../spec/tapeout-plan.md):

| Must-work function | Source | Tree | Readiness block |
| --- | --- | --- | --- |
| POR / cold-start reset | `gf180mcu_ocd_ip__por` @ `a6f16be7`, unmodified | [`por/`](por/) | `monitor` |
| Master bias | `gf180mcu_ocd_ip__biasgen` @ `96a93f81` plus 2 local patches | [`biasgen/`](biasgen/), [`patches/`](patches/); tapeout views in [`biasgen_tapeout/`](biasgen_tapeout/) | `bias` |
| 1.2 V reference | `gf180mcu_ocd_ip__bandgap` from the same biasgen revision, unmodified | [`bandgap/`](bandgap/) | `bias` |
| Per-island bias distribution | new: `pt_bias_root` and `pt_bias_bank{3,4,5,8}` | [`distribution/`](distribution/) | `bias` |

Both upstream cells are Apache-2.0 ([`UPSTREAM.md`](UPSTREAM.md)). Every number
below comes from [`evidence/core_support_evidence.json`](evidence/core_support_evidence.json).
`run_core_support.sh` regenerates that file; see [Reproduce](#reproduce).

Operating envelope (tapeout plan):

- **Function:** tt/ss/ff × 22/32 °C × 3.15/3.35 V, plus tt/27 °C/3.3 V.
- **Safety:** 0 → 3.63 V ramps, brownout, repeated ramps, 0–85 °C.
- **Exploratory only:** −40 °C and 125 °C.

## Verdict

| Block | safe | clean | observable | Summary |
| --- | --- | --- | --- | --- |
| `monitor` (POR) | **pass**, with the plan's system conditions | **pass** | open | Clean reset on every 1 µs–100 ms ramp and on every power cycle. It ignores brownouts that stay ≥ 1.5 V and can miss 1 s ramps (4 of 54 runs). Both gaps go to the board supervisor on `RESET_N`, with `rst_n = porb & RESET_N`. (risk: PWR-02) |
| `bias` (bandgap + patched biasgen + distribution) | **pass** | **pass** (capacitance-only extraction; bandgap LVS needs a PNP device-name mapping) | open | Two local biasgen patches: the `dvdd` pin fix (the vendored pin sits on ground) and `vfb` compensation (vendored loop −28° at 3.3 V, −49° at 5 V, oscillates; patched loop 53–79°, settles in every fast-ramp and enable case). The imported bandgap starts on every 1 µs–1 s ramp at 0–85 °C and gives 1.207–1.219 V. With the whole chain, the 23 switched outputs give 7.6–12.1 µA before the per-die `idac2` trim. ATB0 force of `VBG` (bandgap disabled) is the fallback. (risk: MOD-17) |

`fallback` is `waived_core`. These states match `spec/tapeout-readiness.json`;
see [Readiness](#readiness-four-tests).

## POR (`monitor`)

### Clean

| Check | Result |
| --- | --- |
| Netlist regenerated from the vendored xschem | Identical to the vendored netlist after normalization |
| Magic DRC, `drc(full)` | 0 errors |
| KLayout DRC (PDK `gf180mcu.drc`, FEOL+BEOL+conn+wedge, density excluded) on the vendored GDS | 0 violations |
| Netgen LVS, Magic hierarchical extraction vs schematic | Circuits match uniquely |
| Netgen LVS, vendored GDS read back, flattened and extracted | Circuits match uniquely |
| Cross-check in the digital image (Magic 8.3.623 / Netgen 1.5.316) | DRC 0, LVS match |
| HRES (62/0) on every `ppolyf_u_1k` body of the vendored GDS | 200 of 200 bodies covered (KLayout check `flow/hres_check.py`) |
| PEX | Magic R+C, flat (`extresist`, tolerance 10: 1534 C, 966 R) |
| Extracted simulation, all 13 window points | Pass: one clean release, 32.8–48.6 ms after VDD reaches 90 %. That is +5.2 % to +5.5 % vs schematic. The PEX runs add 1 TΩ / 10 aF node shunts (`rshunt`/`cshunt`); without them, 5 of 13 abort at the release edge. |

### Behaviour (schematic netlist unless marked)

In every case `ena` is tied to VDD and `porb`/`por` each drive 1 pF. "Released"
means `porb > VDD/2` with VDD ≥ 1.0 V.

- **Function window.** Delay after VDD reaches 90 % is 31–46 ms (ff fastest,
  ss slowest). Supply current after release is 1.96–3.59 µA. The hold-off
  node is a 7.2 pF MIM capacitor charged at about 56 V/s, i.e. roughly 0.4 nA.
  It trips at `vcap` ≈ 2.18 V (tt).
- **Ramps to 3.63 V, tt/ss/ff × 0/27/85 °C (54 runs).** (risk: PWR-02)
  - Rise times of 1 µs, 10 µs, 1 ms and 10 ms: clean reset in all 36 runs,
    released 34–55 ms after the ramp starts.
  - 100 ms ramps: reset is asserted first, then released at VDD = 1.36–3.48 V,
    usually before VDD is valid.
  - 1 s ramps: release at 1.05–1.55 V for tt (0/27 °C) and ss. For ff (0, 27
    and 85 °C) and tt/85 °C, `porb` is already high when VDD reaches 1.0 V, so
    3.3 V logic never sees a reset. **4 of 54 runs fail** the "clean reset on
    any ramp" safety criterion. With −40/125 °C (exploratory), ff/125 °C fails
    the same way and ss/−40 °C releases at 1.77 V.
- **Brownout dips after a completed cold start, 10 µs edges.**
  - Dips to 1.5, 2.0, 2.5 or 3.0 V, lasting 10 µs to 100 ms: **no reset**.
    `vcap` follows the rail down and recharges with it.
  - Dips to 1.0 V lasting ≥ 1 ms: reset re-issued with a 17–25 ms hold.
  - Dips to ≤ 0.5 V: reset re-issued with a 19–39 ms hold.
  - Dip to 1.0 V lasting 10 µs: no reset.
- **Power cycle to 0 V.** Off-times from 100 µs to 1 s at tt/27, ss/0 and
  ff/85 °C: reset re-issued every time, with a 28–40 ms hold.
- **Falling rail** (3.3 V → 0 V in 1 ms or 100 ms): `porb` follows VDD down and
  is never asserted while VDD ≥ 1.0 V.

**Conclusion.** The POR is a cold-start and full-power-cycle reset only. That
matches the upstream README ("slow ramps can trip near 1.5 V"). It is not a
brownout detector, and it does not cover ramps slower than about 100 ms. The
cell is safe in itself: it draws a few µA and showed no latch or oscillation in
any case. Per the plan decision (`spec/tapeout-plan.md`, POR / reset row), a
board reset supervisor on `RESET_N` covers slow ramps and brownout. That
external part is not simulated here.

### Required reset integration (for the RTL owner; not implemented here) (risk: PWR-02)

- `rst_n_core = porb & RESET_N_pad`. Assertion is asynchronous and reset
  dominates. Release is synchronized to the clock domain that uses it. For the
  `HOST_SCLK`-only SPI domain, which may have no clock, release asynchronously
  only while `CS_N` is high.
- Put a weak on-chip pull-down on `RESET_N`, so a missing or unpowered host
  holds the die in reset. A pull-down never back-drives the host.
- Board rule (plan decision): a reset-supervisor IC drives `RESET_N`. It holds
  reset until VDD has been valid for at least 1 ms and asserts it on any dip.
  This is the only cover for slow ramps and for brownouts that stay ≥ 1.5 V.
- Observability: an SPI-readable sticky `por_event` bit (set by `porb` low,
  cleared by write) and a live `porb` level on the `DBG_OBS` mux. Do **not**
  connect `vcap` or `por_unbuf` to the analog test bus. ATB switch leakage
  would compete with the ~0.4 nA timing current.

## Bias generator (`bias`)

### Local patches (applied in order to scratch copies; vendored tree unchanged)

1. **`biasgen-dvdd-dvss-pin-alignment.patch`.** As vendored, the top-level
   `dvdd` metal4 pin sits on the frontend `dvss` strap. Extraction of both the
   `.mag` and the vendored GDS merges `dvdd`/`dvss`/`avss`, and the real `dvdd`
   net has no pin. Upstream's own LVS report at this revision ends with "Top
   level cell failed pin matching". Wired as delivered, it would short VDD to
   ground. The patch moves the `dvdd` and `dvss` pins onto the right straps.
2. **`biasgen-vfb-compensation.patch`.** The bandgap-referenced loop
   (`bias_amp_large` → `pbias` → `pstack` → `vfb`/R2) is small-signal
   unstable:

   | Configuration | Phase margin, tt/27 °C |
   | --- | --- |
   | 3.3 V supply | −28° (−8° ss, −41° ff) |
   | Upstream's 5 V `avdd` | −49° |
   | Fine range | −58° |
   | Coarse range | −18° |

   Fine-step transients (5 ns ceiling) confirm a sustained oscillation of
   about 1.6 nA ↔ 3.3 µA, also at 5 V. Fix, keeping the upstream topology: a
   dominant pole on `vfb`. Four separate 100 × 38 µm MIM capacitors (≈ 30 pF)
   connect `vfb` (bottom plates) to `avss` (top plates). They sit above the
   cell and are wired on metal5: from the `C2` bottom-plate via4 strip to
   `vfb`, and through a metal5 hop from the `avss` strap. Each MIM is
   < 10 000 µm² and the bottom plates are separate and ≥ 1.2 µm apart
   (MIMTM.1/8b/11). `C3` (m = 4) is added to the `bias_generator_fe`
   schematic so LVS sees the change.

### Clean

| Check | Vendored | Patched (tapeout source) |
| --- | --- | --- |
| Magic DRC `drc(full)` | 0 | 0 |
| KLayout DRC (GF180 deck, density excluded) | 0 on vendored GDS | 0 on `biasgen_tapeout/gf180mcu_ocd_ip__biasgen.gds.gz` |
| Netgen LVS on the tapeout GDS, flattened | **fail** (`dvdd` pin on ground) | **match uniquely** (with and without tying `dvss` to `avss`), no property errors |
| Netgen LVS, hierarchical (analog image) | fail | match uniquely once `dvss` is tied to `avss`. Untied it fails pin matching (`Top level cell failed pin matching`) because Magic's hierarchical extraction joins `avss`/`dvss` through the shared p-substrate (79 vs 80 nets); the idac1/idac2 and sink pin swaps netgen then lists are symmetry fallout of that non-match, not a pin-label error. The die binds both to VSS. |

LVS is read strictly (`flow/summarize.py` `lvs_result`, gate in
`evidence/core_support_evidence.json#lvs_qualification`, the summarize step
exits non-zero on failure): a comparison passes only with a unique final match
and none of the netgen failure strings (property errors, failed pin matching,
unresolved "do not match", unmatched pins). Tolerated and listed per
comparison: subcell non-matches netgen resolved by flattening, and Magic
auto-named ports (`a_<x>_<y>#`) that netgen itself reports as disconnected.
Required: biasgen hierarchical common-ground, flat GDS, flat GDS
common-ground; bandgap hierarchical and flat with the PNP name mapping. Until
2026-11-09 the summary read only the `Final result` line and recorded the flat
biasgen LVS as a match although netgen also reported a property error: C2
(`pbias`-`vfb` MIM) is drawn 23 × 5 µm, Magic reports it 5 × 23 µm
hierarchically and 23 × 5 µm flat, and the GF180 netgen setup compares
`c_width`/`c_length` independently. Both comparison netlists now get a
canonical MIM orientation (`flow/canon_mim.py`, exact swap to
`c_width >= c_length`, same area and perimeter); all other values are still
compared. The fresh tapeout export the flow checks is XOR-identical to
`biasgen_tapeout/gf180mcu_ocd_ip__biasgen.gds.gz` (Magic GDS bytes differ by
timestamp only).

The schematic netlists the assembly device LVS uses as reference are
published, tracked, in `lvs_reference/` (`SHA256SUMS` checked by
`verification/core_bias_routing/device_lvs_reference.py`) by the `tapeout`
step.
| Digital-image cross-check (Magic 8.3.623 / Netgen 1.5.316) | fail | match uniquely |
| HRES on every `ppolyf_u_1k` body | 106/106 | 106/106 |
| HRES negative control: same layout exported by the canary Magic | — | 0/106 (confirms the check detects the defect) |
| PEX | — | Capacitance only. Magic R+C extraction segfaults on this layout. |

The tapeout views are in `biasgen_tapeout/` (`SHA256SUMS` included):

- GDS and LEF of 468.37 × 100.26 µm (upstream 468.37 × 51.68 µm).
- They were generated by upstream's recipe with the analog image's Magic
  8.3.678 and `cif ostyle gdsii`: standard cells read from the Avalon GDS,
  then `gds write` and `lef write -hide`.
- `patched_sources.tar.gz` holds the patched Magic/xschem tree.

### Behaviour at the single 3.3 V supply

Configuration and loads:

- Supplies: `avdd = dvdd = ref_in = VDD`, `avss = dvss = 0`.
- Sources drive 1.0 V; sinks pull from VDD − 1.0 V.
- `vbg` is an ideal 1.2 V source in these stand-alone biasgen runs. The run with the imported bandgap is in [Bandgap](#bandgap-12-v-reference-bandgap).

**Loop stability (patched, AC loop gain, standard range).** 25 points:
tt/ss/ff × 0/22/32/85 °C × 3.15/3.35 V plus tt/27 °C.

- Phase margin 53–79°, gain margin 21–34 dB.
- At 5 V `avdd` the phase margin is 54°.
- Coarse range (used by the distribution): 79.5–94° over the function window.
  At ss/0 °C/3.15 V (safety range only) the coarse loop has no gain: −41 dB DC,
  saturated. It does not oscillate, but the current is not regulated there.
- **Fine range alone (`ref_sel_fine=1`, `ref_sel_coarse=0`) still has only 25°.
  The register map must forbid it.**

**Fine-step transients.** 400 µs runs with a 5 ns step ceiling.

- **Patched: all 23 settle**, to ≤ 2 % peak-to-peak in the last 50 µs:
  - Cases: 1 µs and 10 µs supply ramps (with `vbg` static or tracking VDD),
    `ena` 0 → 1 and `ref_sel_vbg` 0 → 1 on a settled supply, and a 150 mV
    supply step.
  - Conditions: tt/27 °C, ff/22 °C/3.35 V, ss/32 °C/3.15 V, ff/0 °C/3.63 V,
    ss/85 °C/3.15 V, tt/0 °C/3.35 V, 5 V `avdd`, and the C-only extracted
    netlist.
- **Vendored: all 3 oscillate** (`ref_sel_vbg` enable, 1 µs ramp, 5 V `avdd`).

**DC.**

- **Bandgap mode:** `idac1` code 4 gives 0.79–1.21 µA and `idac2` code 31
  gives 6.1–9.35 µA. Supply sensitivity is 0.3–2.7 %/V. The ±20 % spread is
  the poly resistor R2.
- **Self-referenced mode:** sources too weak (`idac1` code 4 gives 1–9 nA at
  ss and 25–140 nA at tt) and supply-sensitive (420–465 %/V). Sinks give
  54–184 nA per unit at 47–206 %/V. Not usable as the master reference at
  3.3 V.
- **Sink DAC weights are not binary.** The 3-bit sinks give bit0 = 3 units and
  bits 1 and 2 one unit each. The 2-bit sink gives 1 unit per bit. The 5-bit
  source DACs are binary.
- **Start-up:** all 33 ramp runs reach the DC current (self mode
  tt/ss/ff × 0/27/85 °C × 1 µs/100 µs/10 ms, 100 ms, and bandgap mode). There
  is no zero-current state.
- **`ena = 0`:** 2.1 nA total supply current, every output < 0.3 nA.

### Required integration hooks (register map / ATB owners)

- **Register defaults:**
  - `ena = 0`, `ref_sel_vbg = 0`.
  - Normal operation: `ref_sel_vbg = 1`, `ref_sel_coarse = 1`, `idac2` code 10
    (10 µA) into the distribution root.
  - `ref_sel_fine = 1` with `ref_sel_coarse = 0` is prohibited.
- **ATB force:**
  - Force `vbg` from ATB0. This replaces the reference and sets every source
    current.
  - Force a current into `ROOT_REF` to replace the biasgen for all islands.
  - Force out of any `TRK_<island>` to replace one island's trunk.
- **ATB sense:** `ROOT_REF` (≈ 0.92 V) and `TRK_<island>` (≈ 1.98 V at 10 µA).

## Bandgap (1.2 V reference, `bandgap/`)

**Import.** The `gf180mcu_ocd_ip__bandgap` hierarchy is copied unmodified from
the same pinned biasgen revision: `bandgap_unbuffered`, `bg_trim`, `bg_res`,
the class-AB output buffer, the folded-cascode amplifiers, and their
paramcells. It is Apache-2.0. The PNP is the PDK's fixed
`pnp_05p00x05p00_0` cell, and the bandgap's resistors are all `ppolyf_u`,
with no high-R `ppolyf_u_1k`.

**Bias wiring.** The bandgap's two bias pins sink current from PMOS diodes:

- `ibias2_1u` comes from biasgen `bandgap_sink1`, code 7 (5 units, about
  0.6 µA at tt).
- `ibias1_250n` comes from biasgen `bandgap_sink2`, code 3 (about 0.25 µA at
  tt).

These sinks are self-referenced, so the chain has no circular start-up
dependence: VDD → biasgen sinks → bandgap → `vbg` → biasgen sources →
distribution. Even at maximum codes the sinks are weak at 3.3 V, but the
bandgap barely depends on them: 0.25× of upstream's bias currents moves `vbg`
by < 1.3 mV.

### Clean

| Check | Result |
| --- | --- |
| KLayout DRC on the vendored GDS | 0 violations |
| Magic DRC `drc(full)` | 46: 45 "P-diffusion must be over N-well" inside the 9 instances of the PDK's own fixed PNP cell (5 each), and 1 Magic-only MIMTM.2. KLayout passes both areas. |
| Netgen LVS (hierarchical and flattened vendored GDS) | Fails only on the PNP device name. This PDK's Magic tech names the 5 × 5 µm PNP cell `pnp_10p00x00p42` (the analog and digital images both do this); upstream's own report names it `pnp_05p00x05p00`. Mapping the name back gives **match uniquely** on both netlists. |
| GDS export from the current `.mag` with the analog image's Magic (`cif ostyle gdsii`) | Differs from the vendored GDS **only** on PPLUS (31/0), 75 µm² in the PNP area (KLayout XOR), and fails KLayout PP.2 (20). So the **vendored GDS is the tapeout source** for the bandgap. |
| HRES | No high-R resistors in the design (LVS device classes are all `ppolyf_u`). 0 HRES shapes is correct. |
| PEX | Capacitance-only, with the PNP name mapped back in the sim deck; Magic R+C segfaults. |

### Behaviour

- **Trim (thermometer; count of set bits).** At tt/27 °C, `vbg` is 1.138 V at
  count 0, **1.212 V at count 8** (default) and 1.341 V at count 16. Steps run
  4–19 mV and grow with the count.
- **Stand-alone, ideal upstream bias.** `vbg` = 1.204–1.220 V over tt/ss/ff ×
  −40…125 °C. Within a corner it varies only 1–4 mV. Supply current is
  87–161 µA, the largest load in the reference chain.
- **Full chain in the function window** (13 points, plus extracted at tt):
  bandgap + compensated biasgen (coarse, `idac2` code 10) + distribution.
  - Every point starts.
  - `vbg` is 1.207–1.219 V.
  - Distribution outputs are 7.64 µA (ss) to 12.14 µA (ff), tt 9.53–9.66 µA.
  - `vbg` settles to 1 % within 10–20 µs after VDD reaches 90 %.
  - Chain supply current is 0.30–0.52 mA, of which 0.23 mA is the 23 outputs.
- **Start-up, safety range** (biasgen + bandgap, VDD 0 → 3.63 V in 1 µs,
  100 µs, 10 ms and 1 s; tt 0/27/85 °C, ff 0/85 °C, ss 0/85 °C).
  - **All 28 start**; there is no zero state.
  - On 10 ms and 1 s ramps, `vbg` is settled before VDD reaches 90 %.
  - Peak supply current is ≤ 0.42 mA.
- **Fine-step probes** (5 ns step ceiling, 600 µs): bandgap `ena` 0 → 1 on a
  settled supply (tt, ff/22 °C/3.35 V, ss/32 °C/3.15 V) and a 1 µs ramp (tt).
  All settle: `idac2` peak-to-peak ≤ 1.2 pA, `vbg` peak-to-peak ≤ 0.1 mV.
- **ATB0 fallback** (1.2 V forced on `vbg` through the 2.35 kΩ force leaf).
  - With the bandgap disabled (`ena = 0`), its output is high-impedance: the
    force source carries 15–34 pA, `vbg` = 1.200 V, and the chain delivers
    `idac2` = 8.0–11.6 µA (the same resistor spread).
  - With the bandgap enabled, the force fights its buffer (5.1 µA through the
    leaf; `vbg` stays at 1.212 V). **Disable the bandgap before forcing.**

## Bias distribution (`distribution/`)

**Consumers.** 23 10 µA IBIAS outputs from the block READMEs: 22 consumers
plus one reserved. Every consumer sinks its current into an NMOS diode, so
each output is a switched PMOS source.

The pll trunk feeds three `pt_pll_ring` instances (TX/shared, RX CDR,
host_follow) and one reserved output for a possible LC-VCO loop, which stays
off until that loop exists.
`analog/timing/README.md` and `timing/pll_ring.spice` confirm the input:
`pt_pll_ring.IBIAS` sinks 10 µA into an NMOS diode (`XNB`, 4/2 µm, mirrored by
8/2 µm devices), and the timing benches use a 10 µA test source. When the
ring is disabled, `XNBC` clamps `IBIAS` to VSS. A bank output left enabled
into a disabled ring therefore still delivers ≤ 10 µA into the clamp, so each
output's `EN` must follow its ring's `EN`.

| Island trunk | Consumers | Bank |
| --- | --- | --- |
| rf | lna, rxmix_i, rxmix_q, bbfilter_i, bbfilter_q, txmix_i, txmix_q, rfdriver | `pt_bias_bank8` |
| conv | adc_i, adc_q, dac_i, dac_q, refbuf | `pt_bias_bank5` |
| pll | pll_ring_tx, pll_ring_rx, pll_ring_host, lc_vco (reserved) | `pt_bias_bank4` |
| wire | ctle, detect, wiredtx | `pt_bias_bank3` |
| debug | bb_tap_i, bb_tap_q, bb_tap_wmon | `pt_bias_bank3` |

**Topology.**

- The biasgen's `idac2` output (10 µA) feeds the NMOS diode in
  `pt_bias_root`, on the always-on rail.
- The root has five 1:1 NMOS legs, one per trunk, each behind a series switch
  gated by `EN_<island>` (reset 0).
- Each trunk is a current-mode line to its island bank, which sits on the
  island's switched rail. The bank has a PMOS diode and N 1:1 PMOS mirrors.
  Each mirror has a series switch closed only when that block's `EN` is high.
- All devices are 3.3 V with L = 4 µm. Cascodes are omitted: consumer pins sit
  at ~0.95 V and a PMOS diode drops ~1.2 V, so there is no headroom for them
  on 3.3 V.
- Layout uses the shared row generator (`analog/rf_tx/layoutlib.py`, imported,
  not modified). GDS is exported with the analog image's Magic 8.3.678
  (`cif ostyle gdsii`).
- Total cell area is about 43 700 µm² (bank3 counted twice).

| Cell | Size (µm) | Magic DRC | KLayout DRC on exported GDS | LVS |
| --- | --- | --- | --- | --- |
| `pt_bias_root` | 157.7 × 25.1 | 0 | 0 | match uniquely |
| `pt_bias_bank8` | 183.9 × 78.0 | 0 | 0 | match uniquely |
| `pt_bias_bank5` | 176.4 × 50.8 | 0 | 0 | match uniquely |
| `pt_bias_bank3` | 154.4 × 27.3 | 0 | 0 | match uniquely |
| `pt_bias_bank4` | 174.3 × 46.3 | 0 | 0 | match uniquely |

The bank8 enable inverters are 4/8 µm because minimum gates failed antenna
rule ANT.5 on the long EN routes.

**Master voltage references (`pt_bias_vref`, 2026-11-09).** The architecture's
`bias.vref0` (1.0 V, sink `refbuf.VREF0`) and `bias.vcm` (VDD/2, sinks
`adc_i`/`adc_q` `VCM`), ATB codes 2/3, had no source in the core-bias assembly:
the Edwards biasgen/bandgap give currents and `vbg` only (voltgen not
imported). `pt_bias_vref` is passive and always on (core VDD, no control,
reset-safe): `VREF0 = 5/6·VBG` (1 + 5 units of `ppolyf_u_1k` 1 × 40 µm,
~240 kΩ, ~5 µA from the class-AB-buffered `vbg`; 1.010 V at VBG 1.212 V) and
`VCM = VDD/2` (2 + 2 units, ~20 µA, ~40 kΩ Thevenin). Bandgap off → VREF0 = 0;
an ATB0 force of VBG moves VREF0 with it; `conv_vref` (code 36) override
remains the refbuf fallback. 85.9 × 56.0 µm, Magic DRC 0, KLayout DRC 0,
LVS match uniquely, HRES 10/10. Not covered: the VCM sampling-charge
decoupling at the ADC (consumer side), VREF0/VCM noise, and mismatch.

**Simulations** (schematic and C-only extracted; root plus all five banks; 23
outputs):

- **Ideal 10 µA reference.** Every output is 10.06–10.15 µA over the function
  window and nominal. That holds for both netlists and for both consumer models
  (0.95 V source and NMOS diode). Within ±5 % for outputs from 0.2 to 2.8 V; no
  neighbour coupling.
- **Behind the compensated biasgen (coarse, code 10).** Outputs are 7.52 µA
  (ss) to 12.06 µA (ff), tt 9.44–9.56 µA. This is the biasgen's ±20 % resistor
  spread. Per-die trim through the `idac2` code against the `TRK` sense is the
  intended correction.
- **Disabled output or trunk** (0/85 °C, 3.63 V): ≤ 47 pA per output.
- **Island rail at 0 V** with trunk and all EN high: no output current. The
  core rail carries only the 10 µA reference.
- **ATB force.** With all trunks disabled, sinking 10 µA from `TRK_RF` gives
  10.02 µA on all 8 RF outputs and ≤ 12 pA elsewhere.
- **VDD 0 → 3.63 V in 10 µs** (tt/27, ff/0, ss/85, extracted at tt):
  - Enables low: core current ≤ 10.6 µA, outputs ≤ 10 nA peak.
  - Enables high: about 294 µA total, per-output peak ≤ 10.21 µA.

## Register requirements (for the register-file owner)

All fields are core-domain bits from the generated register file. Every reset
value below is the safe state. Normal-operation values are given for the
bring-up sequence.

| Field | Width | Reset | Normal | Notes |
| --- | --- | --- | --- | --- |
| `bias.ena` | 1 | 0 | 1 | biasgen enable; 2.1 nA total when 0 |
| `bias.ref_sel_vbg` | 1 | 0 | 1 | 1 = sources referenced to `vbg` (bandgap or ATB0 force) |
| `bias.ref_sel_coarse` | 1 | 0 | 1 | coarse unit (1 µA); the distribution needs it |
| `bias.ref_sel_fine` | 1 | 0 | 0 | **Forbidden: `ref_sel_fine=1` with `ref_sel_coarse=0`** (25° phase margin). Gate it in hardware: `fine_eff = fine & coarse`. |
| `bias.idac2_source` | 5 | 10 | trimmed, 8–13 | distribution reference into `ROOT_REF`. Code × 1 µA nominal. |
| `bias.idac1_source` | 5 | 0 | 0, or 4 for test | spare 1 µA-unit source; ATB sense output for bench checks |
| `bias.bandgap_sink1` | 3 | 7 | 7 | bandgap 1 µA bias. Non-binary: bit0 = 3 units, bit1 = bit2 = 1 unit. |
| `bias.bandgap_sink2` | 2 | 3 | 3 | bandgap 250 nA bias |
| `bias.voltgen_source`, `bias.voltgen_sink1`, `bias.voltgen_sink2` | 5/3/3 | 0 | 0 | voltgen not imported; outputs unused, keep 0 |
| `bgap.ena` | 1 | 0 | 1 | must be 0 while ATB0 forces `vbg` |
| `bgap.trim` | 5 (count 0–16) | 8 | trimmed | stored as a count and decoded to the 16-bit thermometer `trim[15:0]` (bits 0..count-1 set) |
| `dist.en_rf`, `dist.en_conv`, `dist.en_pll`, `dist.en_wire`, `dist.en_debug` | 1 each | 0 | 1 when that island is powered | root trunk leg enables (`EN_<ISLAND>`) |
| pll bank `EN3` (LC-VCO reserve) | 1 | 0 | 0 | keep 0 until an LC-VCO loop exists; tie to that loop's enable |
| per-block `en` | — | 0 | — | Each block's own enable also closes its bank output switch (`EN<k>`). No separate register. |

**Bring-up sequence.**

1. Island power off, all fields at reset.
2. Set `bias.ena=1`, `bgap.ena=1` (sinks at 7/3, trim 8). The bandgap settles
   in < 25 µs in simulation; wait ≥ 100 µs.
3. Set `bias.ref_sel_vbg=1`, `bias.ref_sel_coarse=1`.
4. Power an island, set `dist.en_<island>=1`, then the block enables.

All enable steps were simulated abrupt with no oscillation. The order keeps
`vbg` valid before the sources use it.

**Per-die trims.** These are applied by host software after every reset; no
non-volatile storage is assumed.

1. **Bandgap.** Sense `VBG` on ATB1 with a high-impedance meter. Step
   `bgap.trim` and keep the count closest to 1.200 V. The tt step size is
   4–19 mV; 1.212 V at count 8.
2. **Distribution reference** (corrected 2026-11-14, interface row PC-10: the
   earlier procedure held `TRK_DEBUG` at 2.0 V with the debug island
   unpowered, which forward-biases the bank's PMOS diode into the dead rail).
   - Set `bias.idac1_source = 10` (the spare source: same 1 µA unit DAC as
     `idac2`) and measure its current on ATB sense code 57 into an SMU held
     at about 1 V. Call it `I_meas`.
   - Set `idac2 = round(100 µA / I_meas)` (the code that gives the nearest
     10 µA). Coarse steps are 1 µA, about ±5 % after trim; codes 8–13 cover
     the simulated 7.6–12.1 µA spread. Set `idac1_source` back to 0.
   - Cross-check, with the bank's rail ON and all its outputs disabled:
     `dist.en_<island>=0`, sink 10 µA from `TRK_<island>` through the force
     leaf and read one enabled output, or read the `TRK` voltage (≈ 2.0 V).

**ATB node list.** Leaves are `analog/island_support` cells: force leaf
`atb_tap_f` to ATB0, sense leaf `atb_tap_s` to ATB1, both in the "core bias/ref"
group.

| Node | Nominal | Force (ATB0) | Sense (ATB1) | Precondition for force |
| --- | --- | --- | --- | --- |
| `VBG` (bandgap out = biasgen `vbg`) | 1.21 V | voltage, 1.2 V | voltage | `bgap.ena=0` (forced node draws ≤ 34 pA) |
| `ROOT_REF` | 0.92 V | current into node, 10 µA | voltage | `bias.idac2_source=0` or `bias.ena=0` |
| `TRK_RF`, `TRK_CONV`, `TRK_PLL`, `TRK_WIRE`, `TRK_DEBUG` | ≈ 2.0 V (island on) | current out of node, 10 µA | voltage | `dist.en_<island>=0` |
| `idac1_source_ibias` (spare) | — | — | current, into an SMU at ≈ 1 V | `bias.idac1_source` ≠ 0 |

## What is not verified (risk: MOD-17)

- **Biasgen extraction.** It is capacitance-only. Magic R+C extraction
  segfaults on it.
- **Bandgap corners.** The bandgap PNP corner is tied to the MOS corner;
  upstream sweeps it independently (±3.6 mV of `vbg` per its documentation).
  Stand-alone biasgen results (`#biasgen`) use an ideal 1.2 V `vbg`; the
  imported-bandgap chain is in `#bandgap`.
- **Bandgap layout.** Magic DRC flags the PDK's own PNP cell. LVS needs the
  PNP device-name mapping. The bandgap tapeout source is the vendored GDS
  (see above).
- **Mismatch and Monte Carlo.** Not run. Island mirror matching has only the
  device sizes.
- **Integration.** Not simulated:
  - the `porb & RESET_N` logic;
  - the board supervisor;
  - register defaults;
  - ATB leaf/group switches;
  - trunk wire RC across the floorplan.
- **POR coverage.** Safety sweeps use the POR schematic netlist. Extracted runs
  cover the 13 function points.
- **Consumer models.** Ideal sources or simple NMOS diodes, not the blocks'
  extracted inputs.
- **Avalon revision.** The one upstream drew against is unknown. DRC/LVS are
  consistent with Avalon @ `b41119fd`.

**Evidence currency.** Every source hash in
`evidence/core_support_evidence.json:source_hashes_sha256` matches the current
files; the evidence is current.

## Readiness (four tests)

States as recorded in `spec/tapeout-readiness.json`. Evidence paths are relative to `analog/core_support/evidence/core_support_evidence.json`.

| Block | Test | State | Evidence |
| --- | --- | --- | --- |
| `monitor` | safe | `pass`, with the system conditions in the plan (`porb & RESET_N`, board supervisor) | `#por.safety_ramps_3v63`, `#por.repeated_ramps`, `#por.brownout_dips`, `#por.falling_rail` |
| `monitor` | clean | `pass` | `#clean.por`, `#por.function_window_pex` |
| `monitor` | observable | `open` | needs the `por_event`/live `porb` register and `DBG_OBS` entries (risk: INT-04) |
| `bias` | safe | `pass` | `#bandgap.startup_safe_range`, `#bandgap.atb0_force_1v2`, `#biasgen.startup`, `#biasgen.bandgap_mode_probes`, `#biasgen.disabled`, `#distribution.disabled`, `#distribution.island_rail_off`, `#distribution.supply_ramps` |
| `bias` | clean | `pass` (C-only extraction; bandgap LVS via the PNP name mapping) | `#clean.bandgap`, `#bandgap.chain_function_window`, `#clean.biasgen_patched`, `#biasgen.bandgap_loop_gain`, `#biasgen.window_currents_pex`, `#distribution.layout`, `#distribution.function_window_ideal_10uA_reference` |
| `bias` | observable | `open` | ATB nodes exist (`ROOT_REF`, `TRK_*`, `vbg`); ATB mux codes and register entries not yet assigned |

## Reproduce

```
projects/programmable_transceiver_platform/analog/core_support/run_core_support.sh
# steps: fetch verify clean tapeout canary dist sim summarize
```

Requirements and behaviour:

- Docker with the pinned arm64 `iic-osic-tools` image and
  `svalbard/librelane-gf180-canary:2026.08`.
- `fetch` is the only step that uses the network: it clones the pinned
  Avalon library.
- Containers run with `--network none`, bounded CPU/memory and
  `OMP_NUM_THREADS=1`.
- Heavy output goes to `scratch/core_support/`.
- Files written into the repo: `evidence/`, `biasgen_tapeout/` and
  `distribution/generated/`.

| Script | Does |
| --- | --- |
| `flow/clean_flow.sh` | DRC, LVS, PEX, tapeout export and the HRES check |
| `flow/crosscheck_canary.sh` | Digital-image DRC/LVS and the HRES negative control |
| `flow/sim_core_support.py` | POR and biasgen simulations, loop gain and probes |
| `flow/sim_bandgap.py` | Bandgap and full reference-chain simulations |
| `distribution/generate_dist.py` | Distribution layout, DRC and LVS |
| `distribution/sim_dist.py` | Distribution simulations |
| `flow/summarize.py` | Writes the evidence file |

## 2026-11-14 additions (pads + core-support owner)

Work and evidence: `scratch/pads-core/` (`NOTES.md`, `corners/`, `bias/EVIDENCE.md`); interface rows PC-5…PC-10.

**Always-on audit follow-up (`scratch/reviews/always-on-audit.md`).**

- **F4, bandgap standby current.** The imported bandgap core runs whenever VDD is present; `bgap.ena` only
  tri-states its output buffer. Reset-state `pt_core_bias` current is therefore **91 µA at tt/27 °C/3.3 V
  (bandgap 71 µA, VCM divider ≈ 20 µA, biasgen 1.2 nA), 131.9 µA at ff/85 °C/3.63 V**, not the nA figure the
  biasgen row alone suggests. Kept as is (vendored, silicon-proven cell; a supply header would change PSRR and
  start-up); the budget owner books it (PC-8). A faulty bandgap is bypassed with the ATB0 force of `VBG`
  (output high-Z at `ena` = 0), not switched off.
- **F5, `VBG` overshoot at enable. Not fixed in hardware.** `VBG` goes to the rail for about 4 µs when
  `bgap.ena` rises (peak 3.18 V tt, 3.02–3.29 V at the corners below, 3.41 V at ss/3.5 V, 3.53 V at ff/85 °C/3.63 V).
  Enabling the biasgen 200 µs before the bandgap does not change it (3.18 V, `corners/F5_bgen_first_tt.log`):
  it is the output buffer's own start. Every node that sees it is a 3.3 V gate or the passive `pt_bias_vref`
  divider and stays ≤ VDD, so there is no overstress; the functional risk is 2.6× output current for a few µs
  if `ref_sel_vbg` and a trunk are already on. Required order (unchanged): `bgap.ena` first, wait ≥ 100 µs, then
  `ref_sel_vbg`. A hardware interlock or an RC between `VBG` and the biasgen input is not built.
- **F7 / pre-mortem 12 (MOD-19), corners that were missing. Extracted netlists.**
  - POR (`layout_pex`, 1 ms ramp), MOS × resistor × MIM corners: release 29.7 / 36.1 / 45.7 / 55.5 ms at tt with
    (res, MIM) = (ff, ff) / (ff, ss) / (ss, ff) / (ss, ss); 25.1–46.3 ms at ss/0 °C/3.15 V; 38.8–73.3 ms at
    ff/85 °C/3.63 V; 51.0 ms at ss/32 °C/3.5 V. One clean release in every run; range **25–73 ms** (was quoted
    31–55 ms with MOS corners only). The two ff/85 °C runs end on the known solver abort just after the release edge.
  - Bias chain (bandgap + biasgen + root + banks + vref, README bring-up order): outputs 9.35 µA (sf) and
    9.56 µA (fs) at 27 °C/3.3 V, `VBG` 1.211 / 1.213 V; with crossed resistor corners 7.94 µA (tt, res_ss),
    11.81 µA (tt, res_ff), 7.98 µA (ff MOS, res_ss), 11.35 µA (ss MOS, res_ff), 7.88 µA (ss, res_ss, 3.5 V);
    `VBG` 1.2057–1.2209 V. The output current follows the poly resistor, not the MOS corner; `idac2` codes
    8–13 still cover it. All start; no stuck state.
  - Not done: brownout and power-cycle POR cases on the extracted netlist; Monte Carlo; R extraction of the
    biasgen and bandgap (Magic R+C still segfaults).

**New cells, published in `distribution/generated/` (generator `distribution/circuits_ext.py`, `generate_ext.py`;
`circuits_dist.py` is untouched so the published bank evidence hashes stay valid).** Evidence
`scratch/reviews/pads-core/CORE-SUPPORT-CELLS.md`; independent review `scratch/pads-core/review-cs/REVIEW.md`; rows PC-5, PC-6, PC-16.
All three: Magic DRC 0, LVS unique on the generator netlist and on the GDS read back from disk (negative controls fail),
precheck decks main 0 / antenna 0 (sha-matched records, registered in `verification/kl_block_drc_blocks.json`), HRES complete.
Extraction is capacitance-only, as for the banks. No LEF abstracts yet.

| Cell | Pins | Size (µm) | What it does | Extracted result |
| --- | --- | --- | --- | --- |
| `pt_bias_tap2` | `VDD VSS TRK EN0 EN1 OUT0 OUT1` | 93.7 × 23.7 | two more switched 10 µA outputs on an existing trunk (no diode) | 10.05–10.20 µA, tap/bank 1.0000 on the same rail; **3.4 % per 10 mV of rail offset: must share the bank's rail** |
| `pt_refvcm` | `VDD VSS EN VCM` | 137.9 × 54.0 | refpad common mode, VDD/2, gated | VCM/VDD 0.4984–0.4992, 15–29 µA, off: 0 V and ≤ 2.3 nA; 40 kΩ source: AC-coupled or complementary pad drive only |
| `pt_txpad_bias` | `VDD VSS EN BUF_REF BUF_BIAS EN_DET IBIAS_DET DETECT_PBIAS` | 167.3 × 61.1 | TX termination buffer REF (VDD/2) and BIAS (3/11 VDD) dividers, gated; TX-pad detect PMOS bias (×5 mirror from a 10 µA input) | REF/VDD 0.4967–0.4984, BIAS/VDD 0.2714–0.2721, ≈ 195 µA on; detect source **49.5–50.8 µA per pad leg** (100 µA needs a wider pad device) |

**Bank rails with ten islands.** A bank or tap must sit on the same rail as its trunk diode (3.4 % per 10 mV of
offset; a trunk whose diode rail is off turns every mirror on it fully on). Proposal PC-5: all bank rails on the
always-on core VDD, outputs gated by their consumer's enable.
