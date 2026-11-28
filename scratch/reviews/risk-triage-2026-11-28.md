# Risk triage, 2026-11-28 (freeze)

Scope: `spec/risk-register.md` rows with status open / demanded-mitigation and score >= 16, minus assembly/floorplan/routing/LVS rows (skipped: INT-13, INT-32, INT-33, INT-34, INT-36, PDN-12, PDN-13, VER-KL2, MOD-06, LO-01, XT-01, SUB-01; AN-01 is not a >= 16 open row). 34 rows triaged. Read-only; the register is not edited.

Counts: **KILLER 3, BLOCK-DEAD 9, PERF 22.**

| ID | Class | Reason | Bypass / fallback | Cheap retire / confirm |
|---|---|---|---|---|
| PWR-12 | KILLER (board-mitigated) | A fast supply edge fires every supply-pad clamp at once: amperes through the bonds, possible overstress; survivability not shown. **Stale/contradicting:** register quotes M6's 5.7-6.4 V; the newer `CLAMP.md` gives 3.48-3.88 V with a stiff source and says the peak is a board property; it also found the worst firing at 3.0-3.5 us (sf/85, slow RC), and at 3.5 V trim a 2 us ramp fires at tt | Board rule B52 (<= 0.3 V/us, soft start >= 100 us recommended, no hot-plug) | Board owner (inactive) confirms regulator soft-start part and that the trimmer cannot step the rail; one bench run with the real board feed network. Update register text to CLAMP.md numbers |
| PDN-02 | KILLER (unproven) | Shared digital macro ripple 212 mV (rf) / 313 mV (wired) vs 150 mV with single-phase launch; the macro runs reset, SPI decode and host link for the whole die. Two-phase launch not built | Reduced clocks (`debug.host_link.rate` div2/div4), supply trim 3.50 V, slow SPI | Run STA/GLS of SPI + reset + host path at div4 with the 313 mV droop applied (or derate) to show the boot path survives; if it does, downgrade to PERF |
| INT-04 | KILLER (debuggability) | Observation taps / ATB / ring-monitor codes not all assigned or wired; a half-working die cannot be told from a dead one and supply trim cannot be chosen (violates the learning/debuggability mandate) | SPI read-back, `status.health.*`, CLK_OBS / DBG_OBS pads, RESET_STATUS | Per-block checklist in `tapeout-readiness.json`: confirm at minimum per-island supply/bias ATB and ring-monitor readout are wired on both chips; the TRK_LO / TRK_WIRED_TX select bits |
| WRX-01 | BLOCK-DEAD | CDR closed loop unproven on published `pt_cdr` r13 | FPGA oversampling; forwarded clock on AUX_CLK | Extracted closed loop at one tt + one ss corner |
| WRX-20 | BLOCK-DEAD | CTLE gain collapses (-8 / -9.6 dB) with real load; r4 fix NO-GO | `wire_ctle_bypass` (RX straight to CTLE output); FPGA path | Simulate chain with CTLE bypassed at ss to confirm slicer still resolves a short channel |
| WRX-02 | BLOCK-DEAD | Slicer fails 2.5 Gb/s at ss, offset trim misses 20 mV, not qualified at the 0.4 V CM | Lower rate, supply trim, oversampling CDR fallback | Requal at 0.4 V CM at 3.50 V trim (one ss run) |
| WTX-08 | BLOCK-DEAD (at ss/full rate) | No wired TX path shown at 2.5-3.24 Gb/s at ss extracted | Lower line rate, 3.50 V trim, legacy quarter-rate TX, WTX_EXT | Rate x corner table at 3.50 V; keep the quarter-rate TX until it exists |
| WTX-09 | BLOCK-DEAD - **stale** | Register says run detector never asserts on the full netlist, cause unknown. Same evidence file (`scratch/wired_tx/s14/QUEUE.md`, later section) found it: extresist substrate-C double count (2-12x); with `fixcap.py`, NO bypass, ss pess 3.15 V, TX_RUN rises at 29.4 ns | Silicon override of the interlock not confirmed (`ilk_bypass` is netlist-only) | Owner (inactive) reruns interlock rows on the fullfix netlist and closes; confirm whether a register force of TX_RUN exists (if not, a detector failure kills the TX bank with no recovery) |
| LO-04 | BLOCK-DEAD | On-chip synthesizer not closed: MMD fails > 2.45 GHz at ss, QVCO top has no netlist/LVS | External LO on REF_IN / AUX_CLK | Owner inactive; confirm external-LO path is LVS-clean and shielded (XT-01, assembly) |
| PWR-13 | BLOCK-DEAD (rescue path only) | With POR_BYPASS strap fitted and RESET_N high, no reset at power-up. Normal boot (strap off, hard pull-down) unaffected | B49 (RESET_N host-drivable, low through ramp), second rescue path: SPI key 0xC3A5 (B51) | Run the not-run brownout / slow-corner ramps of the power-up check; INT-34 PD tie must land in layout (assembly) |
| WRX-08 | BLOCK-DEAD (signal detect) | No jitter / JTOL evidence; signal detect needs threshold redesign; OOB unverified | Ignore detect, FPGA-side idle detect | Decide: ship detect as observe-only |
| MOD-05 | BLOCK-DEAD (meta) | 31/83 blocks' published status unsupported, 21 GDS without precheck DRC: can hide a killer in any block | - | Run `freshness2.py` in the readiness gate; prioritise always-on / shared blocks (POR, bandgap, isolation clamps, pads) |
| MOD-00 | PERF | Umbrella model uncertainty at GHz | Pessimistic bounds, trims, external fallbacks | n/a (characterisation on die 1) |
| DIG-03 | PERF | Cmd/response latency ~2.4x over 400 ns gate | Board USB PHY (B8) | Latency model after timing closure |
| HL-06 | PERF | Host link does not close at full rate on slow dies even at 3.50 V. Note: reset default is full rate, but SPI is independent and sets div2/div4; bring-up rows quote div4 as fine | div2 / div4, FPGA per-die training | GLS at div4 on ss already locks; just confirm bring-up doc starts at div4 |
| LO-11 | PERF | QVCO regulator not qualified for supply-pushing spurs | External LO | - |
| MOD-21 | PERF | Drawn-R / C-only rows optimistic. **Partly contradicted:** QUEUE.md says the rcov audit's C figures carry the same substrate over-count, so its RC failures are overstated | Labelling rule | Re-run rcov C with `fixcap.py` |
| MT-01 | PERF | Well-proximity / LOD offset on slicer, CML | Trim >= +-40 mV | - |
| PKG-05 | PERF | External-LO amplitude vs pad C / package resonance | Adjustable board LO level | - |
| PKG-06 | PERF | Board decap reachable only through 8 x 1 uF | On-die decap plan | Feeds PDN-02 |
| PKG-07 | PERF | No thermal plate, glob-top | Board thermal path, per-mode dwell | - |
| PKG-08 | PERF | Host SSN with real ground bonds | D2H slew/drive limit, deskew, div4 | - |
| RFR-01 | PERF | RX NF 6.3-15 dB vs 4.1 dB | Board fallback LNA | - |
| RFR-05 | PERF | IIP3 marginal / blockers unverified | - | - |
| RFR-11 | PERF | S11 -8.6 to -9.8 dB vs -10 dB, per-board tuning | Per-board carrier network | - |
| RFR-13 | PERF | Board match not buildable on COB as assumed | Higher on-chip Rin, fallback LNA | Simulate fallback-LNA path |
| RFT-01 | PERF | TX output < 0 dBm at ss | Bias/drive cal, external PA | - |
| RFT-03 | PERF | TX EVM/ACLR/mask unverified | Back-off | - |
| RXR-01 | PERF | Pre-filter headroom / AGC range | TIA steps, LNA attenuation | - |
| TIM-13 | PERF | Ring phase spacing up to 67 ps vs +-20 ps | TX trim codes | - |
| WRX-04 | PERF | SATA Gen2 return loss fails through COB | Other standards pass | - |
| WRX-19 | PERF | DP HBR JTOL proven only in a model | Lower-rate standards | - |
| WTX-03 | PERF | Swing / DJ miss at ss/3.15 V | 3.50 V trim | Report trimmed-supply rows |
| XT-08 | PERF | LO bond leakage into RF_RX at 4 Vpp | ~1 Vpp LO drive, REF_IN/BB_Q swap | - |

## KILLER candidates needing action before tapeout, ranked

1. **PDN-02**: the shared digital macro carries reset, SPI and the host link on both chips, and its supply ripple is 1.4-2.1x over the limit with nothing built to fix it. Cheapest check: a ripple-derated timing check of only the boot path (reset, SPI, div4 host link). If that passes, downgrade to PERF; if it fails, the two-phase launch or clock gating becomes a must-do.
2. **INT-04**: without observation, a die that half-works looks the same as a dead one, and the supply trim cannot be chosen. That defeats the debuggability-first goal on both chips. Action: a minimum wired-observation set (island supplies and bias through the ATB, ring monitors, the two trunk select bits) checked line by line.
3. **PWR-12**: this can physically damage the die, but a board rule (B52) already covers it. The register text is stale and should take the `CLAMP.md` numbers. Action: the board owner (no agent active) confirms the regulator soft start and that the trimmer cannot step the rail.

Watch item (not ranked as a killer): WTX-09. The row is stale (the cause was found and fixed in the evidence), but nobody has confirmed whether the interlock has an override on silicon. If it has none, a detector failure would turn off the wired TX bank with no way to recover it.
