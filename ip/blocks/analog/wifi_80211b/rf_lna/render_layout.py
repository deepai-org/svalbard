#!/usr/bin/env python3
"""Render the physical Wi-Fi LNA risk macro for review."""
from pathlib import Path

import pya


layout = pya.Layout()
layout.read("/work/wifi_lna_cs_core.gds")
view = pya.LayoutView()
view.show_layout(layout, True)
view.select_cell(layout.top_cell().cell_index(), 0)
view.add_missing_layers()
view.max_hier()
view.zoom_fit()
view.save_image("/work/wifi-lna-cs-core-layout.png", 1600, 1200)
assert Path("/work/wifi-lna-cs-core-layout.png").stat().st_size > 10_000
