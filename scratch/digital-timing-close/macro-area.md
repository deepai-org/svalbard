# Digital macro area (digital owner, 2026-11-18)

**Outline of record: 1716 x 1640 um = 2.814 mm2** (core 2.736 mm2). Run r8d is routed at this size (79.5 %
utilisation at the end of the flow, detailed routing 0 violations, DRC 0, LVS match). Timing is not closed at
ss_032C_3v15 (`NOTES.md`). 3.20 mm2 is not needed for routing. A probe at 1716 x 1562 = 2.68 mm2 placed and
globally routed at 81.4 % but with clearly worse timing; it was not taken through detailed routing.
Cells after CTS and repair 2.123 mm2 (77.6 %), the basis of the tables below.

## Where the cells are (r8d, after CTS and timing repair, mm2)

| class | area | count |
|---|---|---|
| combinational logic (after sizing) | 0.775 | 30,400 |
| flops | 0.720 | 10,062 |
| buffers inserted by the flow (fanout trees 0.24, wire repeaters 0.07, slew / cap, ports, setup, hold) | 0.389 | 13,900 |
| clock tree buffers | 0.132 | 1,208 |
| tap and endcap cells | 0.081 | 18,500 |
| inverters, ties, synthesis buffers | 0.026 | 2,100 |
| total | 2.123 | |

By cell type the largest are dffrnq_1 0.34, **mux2_2 0.21 (6,470 cells: the hold path of every enabled flop;
the library has no enable flop)**, dffq_1 0.20, dffnrnq_1 0.14, buf_8 0.14, clkbuf_16 0.13.

## By module (run r8c, same outline and netlist, after CTS and timing repair; inserted buffers charged to the driver's module)

| module | mm2 | share | of which inserted buffers | flops |
|---|---|---|---|---|
| `digital.control.regs` | 0.3393 | 15.7% | 0.0789 | 1649 |
| `digital.core.ingress` | 0.2586 | 12.0% | 0.0548 | 1645 |
| `digital.core.egress` | 0.2361 | 10.9% | 0.0433 | 1522 |
| `CLOCKTREE` | 0.1757 | 8.1% | 0.0002 | 2 |
| `digital.core.lc_tx` | 0.0957 | 4.4% | 0.0152 | 389 |
| `TAP/ENDCAP` | 0.0814 | 3.8% | 0.0000 | 0 |
| `digital.core.lc_rx` | 0.0776 | 3.6% | 0.0137 | 378 |
| `host.h2d` | 0.0625 | 2.9% | 0.0062 | 500 |
| `wrx` | 0.0601 | 2.8% | 0.0053 | 399 |
| `digital.control` | 0.0485 | 2.2% | 0.0235 | 148 |
| `digital.fca` | 0.0464 | 2.1% | 0.0031 | 278 |
| `digital.fcb` | 0.0461 | 2.1% | 0.0033 | 276 |
| `digital.control.spi` | 0.0454 | 2.1% | 0.0052 | 63 |
| `digital.core` | 0.0416 | 1.9% | 0.0088 | 234 |
| `usb` | 0.0404 | 1.9% | 0.0045 | 273 |
| `digital.core.frame_rx` | 0.0378 | 1.7% | 0.0053 | 267 |
| `digital.core.frame_tx` | 0.0364 | 1.7% | 0.0045 | 239 |
| `digital.prbs_check` | 0.0353 | 1.6% | 0.0024 | 190 |
| `(top:debug_cfg_ra)` | 0.0289 | 1.3% | 0.0071 | 143 |
| `(top:analog_cfg_r)` | 0.0287 | 1.3% | 0.0067 | 124 |
| `(top:por_path/rst)` | 0.0251 | 1.2% | 0.0250 | 0 |
| `digital.core.collect` | 0.0172 | 0.8% | 0.0016 | 116 |
| `host.gearbox` | 0.0158 | 0.7% | 0.0006 | 143 |
| `monitor` | 0.0142 | 0.7% | 0.0015 | 90 |
| `digital.interp.lane` | 0.0133 | 0.6% | 0.0003 | 104 |
| `digital.core.unpacker` | 0.0129 | 0.6% | 0.0015 | 64 |
| `digital.core.packer` | 0.0117 | 0.5% | 0.0026 | 63 |
| `wtx` | 0.0114 | 0.5% | 0.0010 | 72 |
| `digital.prbs` | 0.0112 | 0.5% | 0.0017 | 34 |
| `(top:analog_cfg)` | 0.0108 | 0.5% | 0.0028 | 0 |

r8c carried 0.044 mm2 more clock buffers than r8d (an abandoned CTS clustering setting); the other rows are
the same within run-to-run noise.

- Register file 0.34: 830 stored bits, 663 of them with a shadow rank (transactional commit with rule checks),
  1,741 enable muxes, the read mux.
- The two transport banks 0.49: 2 x 28 x 40 flop arrays that are also the capture / playback memory, each with an
  enable mux per bit and THREE parallel 28:1 read trees with registered partial results (added for timing).
- The 130 isolation clamps are 0.003 mm2 (count x cell area); monitors 0.014; pattern generator and checker 0.047; both frequency
  counters 0.093; USB 0.040.

## What changed against r7 (3.20 mm2 did not route at 71 %)

| | r7b / r7c | r8d |
|---|---|---|
| half-perimeter wire after CTS | 7.9 m (r7c) | 6.1 m |
| routed length (global) | 16.7 m, did not converge | 8.6 m |
| cells after the post-placement repair | 1.969 mm2 | 1.86 mm2 |
| cells after CTS + repair | 2.225 (r7b), 2.241 (r7c) | 2.123 |

## Levers not taken, largest first (none removes a capability)

| lever | cells saved | what it takes |
|---|---|---|
| Gated clocks instead of enable muxes on the transport banks (2,240 mux2_2) | 0.07 + their enable buffer trees | a clock gate from characterised cells (falling-edge flop + AND2; the characteriser does not handle the library's latch-based gate), 56 gated subtrees through CTS, hold at the bank inputs |
| The same on the register file (1,741 mux2_2) | 0.06 | the write decision is taken on the last data bit, half an SCLK period before the write edge: needs a latch gate or a restructured write |
| One read tree with a two-entry skid instead of three parallel trees in each transport bank | ~0.10 | CDC FIFO read path redesign (stale prefetch of entries not yet written), formal / exhaustive check |
| Direct (no shadow) fields for static trims | 0.03-0.05 | generator support for "direct but locked while ENABLE" |
| Fanout-tree gain 4 -> 6..8 | up to 0.1 | slower high-fanout nets; only after the depth-critical paths are pipelined |
| Reset-less flops where a reset is not needed | ~0.02 | per-block review |
Latches for the static configuration rank need latch timing models first (the characteriser skips latch cells).
Sharing the pattern checker, monitors and counters between modes is already done (one of each, mode-muxed).

## Shape and pins

Width 1716 um is set by the two hand-placed host-link blocks (D2H 11 lanes on the south edge, H2D 10 lanes on
the north edge) and the 835 pins; height is free in steps of 7.84 um (`hio_shift.py`). At 2.81 mm2 the pin
edges are not the limit (port nets are 1 % of the wire). A wider, lower shape needs the two blocks regenerated
and has not been tried.
