#!/usr/bin/env python3
import os
from pathlib import Path
import klayout.db as db
import klayout.lay as lay

cell = os.environ.get("VCO_BAND_CELL_NAME", "cml_vco_band")
output = os.environ.get("VCO_BAND_RENDER_PATH", "/work/cml-vco-band-layout.png")
layout = db.Layout()
layout.read(f"/work/{cell}.gds")
view = lay.LayoutView()
view.show_layout(layout, True)
view.max_hier()
view.zoom_fit()
view.save_image(output, 2400, 1200)
assert Path(output).stat().st_size > 20_000
