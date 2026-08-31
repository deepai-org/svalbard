#!/usr/bin/env python3
"""Render the selected dual-control pulse layout for review."""

from pathlib import Path

import klayout.db as db
import klayout.lay as lay


layout = db.Layout()
layout.read("/work/selected_dual_control_pulse.gds")
view = lay.LayoutView()
view.show_layout(layout, True)
view.max_hier()
view.zoom_fit()
view.save_image("/work/selected_dual_control_pulse-layout.png", 2400, 1500)
assert Path("/work/selected_dual_control_pulse-layout.png").stat().st_size > 10_000
