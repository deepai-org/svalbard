# Shared-resource and consolidation decisions

These decisions reduce the number of distinct designs, die area and current
without dropping any of the 17 target interfaces, fallback routes, debug
access or stretch goals. Decision IDs (`1`–`9`, `P2-*`, `P3-*`) are stable
identifiers referenced from the architecture, register map, RTL and block
READMEs.

Constraints:

- RF and wired payloads are never active together. Within RF mode, TX and RX
  stay warm for turnaround. ADC/DAC sharing that would interrupt turnaround is
  excluded.
- Share slow sources and reusable circuit designs, not a universal RF/serial
  switch fabric. RF and wired pads, protection, LNA/mixers, termination/EQ and
  line drivers stay specialized.

## Clocking architecture

| ID | Decision | Effect |
|---|---|---|
| P3-2 | **One PLL design, `pll_ring`** (compact 4-stage pseudo-differential ring, 8 native phases at 45°), instantiated for wired TX, the wired RX CDR and the host-follow converter/host clock. The generic `pt_pll` is retired. | Ring covers 480–810 MHz at all 12 envelope corners. |
| `wired-rate` | **Selectable 1, 2 or 4 bits per ring cycle** for the serializer and deserializer, so the ring always runs at 480–810 MHz. | See the rate table below. |
| `wired-cdr` | **CDR without a phase interpolator.** Full rate (480–810 Mb/s, including USB HS bursts): 8 ring phases oversample each bit, and digital logic picks the phase. Half and quarter rate: dual-loop CDR on its own `pll_ring` instance, with a frequency loop to the reference and then a bang-bang phase loop. External clock on `WCLK_IN` is the fallback. | RX timing stays independent of TX for full duplex. |
| P3-3 | **Passive external quadrature LO** is the RF baseline: board I on `REF_IN`, Q on `AUX_CLK`, AC-coupled and biased straight onto the mixer gates through `lo_ext`. Converter, sample and host clocks come from a `pll_ring` locked to the FPGA-forwarded `H2D_CLK` (`host_follow`), then `prescale`. | No active circuit in the RF LO path. |
| P3-4 | Autonomous RF LO: LC VCO at 2.45 GHz → passive RC polyphase → `lo_ext` passive switch path, with `prescale` as first feedback divider. | **Under evaluation.** The PDK has no inductor model. |
| P3-1, P3-9 | `quadrature` and `clocktree` are retired. Word clocks come from the fast-cell `wordclk` divider (÷5/10/20). Slow clock functions are in `rtl/pt_clocktree_slow.sv`. Lower-band LOs use ring PH0/PH2 or external I/Q. | −8.84 mA (quadrature), ~0.14 mm² and 6–8 mA (clocktree). |
| P3-5 | `clockmux` carries clocks ≤1 GHz only, with no RF LO domain. | 0.32 mA in RF mode, 1.35 mA in wired mode. |
| P3-8 | `vco_replica` is built from the same cells as `pll_ring`. | Representative characterization structure. |

| Rate | Bits per ring cycle | Ring clock |
|---|---|---|
| 480 Mb/s (USB HS) | 1 | 480 MHz |
| 742.5 Mb/s | 1 | 742.5 MHz |
| 1.25 Gb/s | 2 | 625 MHz |
| 1.485 Gb/s and 1.485/1.001 Gb/s | 2 | 742.5 / 741.8 MHz |
| 1.5 Gb/s | 2 | 750 MHz |
| 1.62 Gb/s | 2 | 810 MHz |
| 2.5 Gb/s | 4 | 625 MHz |
| 2.97 Gb/s (HDMI 1080p) | 4 | 742.5 MHz |

External wired clocks on `REF_IN` or `WCLK_IN` therefore carry ring-rate clocks
of up to about 0.81 GHz.

## Merged and shared blocks

| ID | Decision | Effect |
|---|---|---|
| 1, 2 | **One I/Q baseband filter bank (`bbfilter_i/q`) for both directions**, with the PGA as its first stage. It is switched between RX channel filtering and TX reconstruction, and also offers `rx_direct` and DAC-direct-to-mixer bypasses. Simultaneous filtered RX and TX is given up; every RF target is TDD, and loopback calibration uses one filtered direction plus the bypass. | Replaces `rxfilter`, `txfilter` and `pga` (about 1 mm²). |
| 4 | **TMDS is a configuration of `wiredtx`** and the pad output stage: current-steering, on-chip termination off, external 3.3 V pull-ups. | Replaces `tmds`. |
| 5, P2-4 | **USB reuses the wired path.** HS receive uses `slicer`. Squelch, disconnect and FS/LS receivers use `detect`. HS/FS drive, pulls and high-side devices are in the `wirepad` attachment. The HS bias DAC is the `wtx_idac` design (P3-12). | Replaces separate `usbhs`, `usbfs` and `usbdrive` designs. |
| 6 | **One differential clock receiver design (`diff_clk_rx`)** for `refinput`, `AUX_CLK`, `WCLK_IN` and `WTX_EXT`. | 4 instances, 1 design. |
| 7 | **One analog observation buffer (`bb_tap`)** for `BB_I`, `BB_Q` and `WMON`. | 1 design. |
| 8 | Analog `clk_obs` only for `CLK_OBS` and `WCLK_OBS`. `DBG_OBS0/1` and `WDBG_OBS` are register-file status muxes driving plain digital pads. | ≈0.22 mm². |
| P2-5 | **One bias trunk per island** (rf, conv, pll, wired, debug) from the bandgap-referenced biasgen into switched local mirror banks. Disabled blocks draw no bias. | 23 outputs from 5 trunks. |
| P2-6, P3-6 | **One pattern generator and checker in `pt_digital`.** The analog–digital wired boundary is a 20-bit double word at ≤125 MHz, bit 0 first, clocked through clock-gate cells. | Closes timing at ss. |
| P3-7 | **Generalized frequency counter** (`pt_freq_count`, two instances), with a source select over both rings, `ring_osc`, `vco_replica`, `aosc` and the LC prescaler. It provides PLL lock status and the CDR's frequency-to-phase handover. | Every oscillator is readable over SPI. |
| P2-8 | **USB island merged into the wired island**, and a **debug island** added so a broken debug buffer can be cut off its functional node. | 5 island switches: wired, rf, pll, conv, debug. |
| P2-2 | Register fields with no hardware read as zero. Addresses and the SPI ABI are unchanged. | Register file ≈0.30 mm². |
| P2-7 | New static control decode in standard cells. Custom cells only for GHz paths. | — |
| P3-10 | Neighbouring debug pads share protection (BB_I + BB_Q, WTX_EXT + WMON) through rail and return buses at least 40 µm wide. | ≈0.21 mm². Drawn at top-level assembly. |

## Area and current bookkeeping

- `analog-architecture.json` books measured extracted currents and areas
  wherever evidence exists (P2-1, P3-13). Its `area_reallocation_log` records
  every move. Merged and retired blocks keep their names with `merged_into`
  notes so the behavioral model still resolves them.
- Freed area is used, in order, for:
  1. debug cells and debug-pad protection;
  2. pad shunts;
  3. on-chip decoupling (1 nF needs about 1.1 mm² of MIM);
  4. fast-cell rebuilds of blocks failing at ss;
  5. margin.
- Current per mode is in `power-partition.md`. External-clock RF is the
  qualified RF case and is under its ceiling. Autonomous RF exceeds 240 mA and
  is a separately qualified option.

## Under evaluation

| Candidate | Potential | Open question |
|---|---|---|
| P3-4 LC VCO + passive polyphase | Autonomous RF LO | Spiral inductor model, swing at the mixer gates, current |
| MIM decoupling over the digital macro | Up to the macro area | The hardened macro uses flip-flop arrays, not SRAM macros, so MIM-over-SRAM (decision 9) does not apply. A Metal1–Metal4 routing variant frees Metal5 but has 2 antenna violations and worse timing. |
| P2-11 per-mode host I/O current | 40–60 mA | Provider pad crowbar data |

## Rejected

| Candidate | Reason |
|---|---|
| Shrinking the capture/playback memory | User decision: keep it. It sets the SPI-only (MCU) capture depth. |
| ADC↔DAC or I↔Q converter sharing | Interrupts RF turnaround. |
| Shared RF and wired pads or front ends | Matching and loading requirements differ. |
| One debug clock input for both die edges | A GHz clock would cross the whole die. |
| Shared RF RX/TX mixers | Different topologies; little area to gain; GHz switch loading. |
| ADC/slicer comparator sharing | Different common modes; USB needs slicer and detect at the same time. |
| Dropping `vco_replica` or merging it with `ring_osc` | Both are required characterization structures with different purposes. |
| Removing `aux_clk_rx` | Matches I/Q pad loading for the passive LO. |
| Ring at 4.9 GHz ÷2, or LC VCO at 4.9 GHz with TSPC ÷2 | Ring tops out near 1.1 GHz; TSPC fails at 4 GHz. |
| Shared VCM cell | I/Q coupling risk for about 33 µA saved. |
| SAR logic moved into `pt_digital` | It must sit next to the comparator. |
| Custom RX word-capture block `wordcap` | Bit errors after extraction, 0.27 mm², 26–39 mA. RX capture is built in compact cells next to the slicer. |
