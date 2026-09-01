#!/usr/bin/env python3
"""Structural checks for the capture-owned, state-free event lowering."""

import compile_event_capture_state_free as candidate


source = candidate.compile_source()
assert source.count("XWRITE HCLK WSEL ESEL VDD VSS START END hclk_select_window") == 1
assert source.count("XSF0 START SFB") == 1
assert source.count("XSF1 SFB SFDRV") == 1
assert source.count("XSENSE SFDRV SSEL SENSE") == 1
assert source.count("XBOOST SFDRV BOOST") == 1
for forbidden in ("XHSN ", "XSTATE ", " ESTATE ", "XLC0 ", "XSB1 "):
    assert forbidden not in source, forbidden
print("event capture state-free structure: PASS")
