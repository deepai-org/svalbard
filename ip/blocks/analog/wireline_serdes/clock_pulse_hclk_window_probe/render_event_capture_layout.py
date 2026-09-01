#!/usr/bin/env python3
"""Render the selected full-duty event/capture-clock macro."""

from pathlib import Path

import klayout.db as db
import klayout.lay as lay


layout = db.Layout()
layout.read("/work/retimed_event_capture_bridge.gds")
view = lay.LayoutView()
view.show_layout(layout, True)
view.max_hier()
view.zoom_fit()
view.save_image("/work/retimed_event_capture_bridge-layout.png", 2400, 1500)
assert Path("/work/retimed_event_capture_bridge-layout.png").stat().st_size > 10_000
