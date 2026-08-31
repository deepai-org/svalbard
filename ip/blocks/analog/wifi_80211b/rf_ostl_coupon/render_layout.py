#!/usr/bin/env python3
"""Render the die-side Wi-Fi RF calibration coupon for human review."""
from pathlib import Path

import pya

layout = pya.Layout()
layout.read("/work/wifi_rf_ostl_coupon.gds")
view = pya.LayoutView()
view.show_layout(layout, True)
view.select_cell(layout.top_cell().cell_index(), 0)
view.add_missing_layers()
view.max_hier()
view.zoom_fit()
view.save_image("/work/wifi-rf-ostl-coupon-layout.png", 1800, 1250)
assert Path("/work/wifi-rf-ostl-coupon-layout.png").stat().st_size > 10_000
