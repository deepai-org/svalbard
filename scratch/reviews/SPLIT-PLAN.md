# Two-chip split: plan

Decision (user, 2026-11-19): the design becomes two independent chips on two wafer.space Run 3 slots, each
self-sufficient (own power-up, reset, SPI, host link to the FPGA, bias, debug), neither depending on the other.

- **pt_rf**: RF receive, RF transmit, LO synthesis (QVCO, dividers, LO regulator), external-LO input, ADC/DAC I/Q,
  baseband filter/TIA, RF test structures.
- **pt_wired**: wired RX (CTLE, slicer, capture, CDR ring, phase trim, detect), wired TX (fast path, ring, USB
  and 100BASE-TX drivers), forwarded/AUX clock, wired monitors, speed test structures.
- **Both** (instantiated twice from the same source, never copied): POR and strap, SPI, host link, digital macro
  (two configurations of one RTL), core bias, island switches, ATB/test bus, reference input, decap, pad ring.

Goal of the restructure: two chips that each fit with margin, built from ONE block library and ONE RTL source,
with no forked copies and no stale single-chip files left behind.

## Rules for the restructure (coordinator)

1. **No forks.** Blocks stay in `analog/<family>/` and are instantiated by both chips where needed. RTL stays one
   tree; per-chip differences are a parameter / generated config, not a copied file.
2. **One owner at a time for structure.** Phases 1–3 are done by one restructure agent; block owners do not
   restart until phase 3 is committed. Block work against the old single top is frozen (nothing is running now).
3. **Mechanical first, design second.** The split itself changes connectivity and bookkeeping only. Design
   improvements the split enables (more ground bonds for the LNA, full decap, smaller macros) come after, as
   normal owner work with normal review.
4. **Delete, don't archive.** `pt_chip.conn`, the single-chip bond map, die-fit ledger and skeleton are replaced in
   the same commit that introduces the per-chip versions. Git history is the archive.
5. **Every check keeps passing at every commit**, for both chips: chip-top regression, digital regression,
   contract, performance requirements. A check that only made sense for one chip is converted, not dropped.

## Phase 0: freeze and audit (read-only)

- Assignment table: every instance in `pt_chip.conn` (241), every register field, every pad, every spec row in
  `spec/performance-requirements.md`, every interface-changes row still open, every risk-register row, tagged
  rf / wired / both. Anything ambiguous listed with the reason.
- **Cross-mode audit:** every mode in the mode walk and `check_top_modes.py`: does it use blocks from both
  halves? (Examples to check: ADC used to observe wired-side analog nodes or eye scan; ATB measurements that
  route through the ADC; shared AUX clock pair; the WTX_EXT fallback; external-LO pads near wired pads; USB
  using any RF-side block; characterization cells.) Each hit gets a resolution: duplicate the small block, or
  accept the mode on one chip only with a stated reason.
- Digital: which RTL modules each chip needs; the register map split (recommendation: one address map, fields of
  the absent half read 0 and are marked absent per chip; a chip-ID register so software tells them apart).
- Output: `scratch/reviews/split/assignment.md`. No tree changes.

## Phase 1: connectivity and bookkeeping

- `integration/chips/{rf,wired}/` each with `chip.conn`, bond map, `run.sh`; shared check scripts
  (`check_top.py`, `iso_audit_top.py`, `gen_pt_chip.py`) take the chip as an argument. Remove
  `integration/top/pt_chip.conn` in the same commit.
- Each chip's pad ring designed on technical merit from the full 74 sites (user does not care which pad has
  which function): host link + SPI + strap + reference + supplies + that chip's signals; spare sites go to
  ground/supply bonds first (LNA ground and QVCO on pt_rf; HS drivers on pt_wired).
- `spec/contract.json` and the chip-IO checks per chip; `spec/performance-requirements.*` rows tagged by chip.
- Make targets: `transceiver-*` gain a chip variant; the old single-chip target is removed or points at both.

## Phase 2: digital

- One RTL tree; top configuration per chip (`PT_CHIP` parameter or generated config selecting the transport
  owners, wired line coding, USB, IQ packing, monitors, isolation clamps of the islands present).
- Two hardening configs (`verification/digital_hardening/{rf,wired}/`), each sized from its own cell area.
  Expect both well under 2.81 mm²; the D2H hand-over fix (DG8-6) applies to both.
- Full regression for both configurations; register map regenerated with the per-chip view.

## Phase 3: floorplan and signoff per chip

- Die-fit ledger and packer per chip (measured, as the current ledger), including the full 5.4 nF decap plan and
  routing channels. Report margin per chip.
- Sign-off skeleton per chip (fill keep-outs, precheck, top DRC/LVS) using the existing flows parametrised by chip.

## Phase 4: resume block work

Owners restart against their chip's conn, bond map and floorplan. Re-open the decisions the split changes:
LNA ground (dedicated VSS bonds now possible), decap-vs-area, QVCO placement, wired TX island current, the
area-lever list (most become optional).

## Not changed by the split

Operating window, verification discipline, evidence rules (R+C extraction, sf/fs, real neighbours), the ESD
option A decision, per-chip supply trim, COB packaging, and all open block defects.
