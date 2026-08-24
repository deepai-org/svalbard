#!/usr/bin/env python3
"""Render the generated clock-pulse GDS as a reviewable PNG."""

from pathlib import Path

import klayout.db as db
import klayout.lay as lay


layout = db.Layout()
layout.read("/work/clock_pulse_generator.gds")
view = lay.LayoutView()
view.show_layout(layout, True)
view.max_hier()
view.zoom_fit()
view.save_image("/work/clock_pulse_generator-layout.png", 2400, 1500)
assert Path("/work/clock_pulse_generator-layout.png").stat().st_size > 10_000
