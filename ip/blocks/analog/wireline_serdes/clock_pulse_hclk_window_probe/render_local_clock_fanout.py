#!/usr/bin/env python3
"""Render the exact GDS used for local clock-fanout extraction."""

from pathlib import Path

import klayout.db as db
import klayout.lay as lay


layout = db.Layout()
layout.read("/work/local_clock_fanout.gds")
view = lay.LayoutView()
view.show_layout(layout, True)
view.max_hier()
view.zoom_fit()
view.save_image("/work/local_clock_fanout-layout.png", 2400, 1500)
assert Path("/work/local_clock_fanout-layout.png").stat().st_size > 10_000
