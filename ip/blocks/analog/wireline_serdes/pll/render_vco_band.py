#!/usr/bin/env python3
from pathlib import Path
import klayout.db as db
import klayout.lay as lay

layout = db.Layout()
layout.read("/work/cml_vco_band.gds")
view = lay.LayoutView()
view.show_layout(layout, True)
view.max_hier()
view.zoom_fit()
view.save_image("/work/cml-vco-band-layout.png", 2400, 1200)
assert Path("/work/cml-vco-band-layout.png").stat().st_size > 20_000
