#!/usr/bin/env python3
"""Render the routed LNA-to-mixer Wi-Fi parent for review."""
from pathlib import Path

import pya


layout = pya.Layout()
layout.read("/work/wifi_rx_external_lo_parent.gds")
view = pya.LayoutView()
view.show_layout(layout, True)
view.select_cell(layout.top_cell().cell_index(), 0)
view.add_missing_layers()
view.max_hier()
view.zoom_fit()
view.save_image("/work/wifi-rx-external-lo-parent-layout.png", 1800, 1200)
assert Path("/work/wifi-rx-external-lo-parent-layout.png").stat().st_size > 10_000
