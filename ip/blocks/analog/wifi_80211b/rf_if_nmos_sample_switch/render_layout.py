#!/usr/bin/env python3
"""Render the physical differential NMOS sampling-switch baseline."""
from pathlib import Path

import pya

layout = pya.Layout()
layout.read("/work/wifi_if_nmos_sample_switch.gds")
view = pya.LayoutView()
view.load_layout("/work/wifi_if_nmos_sample_switch.gds", 0)
view.max_hier()
view.save_image("/work/wifi-if-nmos-sample-switch-layout.png", 1600, 1200)
assert Path("/work/wifi-if-nmos-sample-switch-layout.png").stat().st_size > 10_000
