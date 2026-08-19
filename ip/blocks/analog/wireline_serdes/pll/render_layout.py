#!/usr/bin/env python3
from pathlib import Path
import os
import klayout.db as db
import klayout.lay as lay

layout = db.Layout()
cell = os.environ.get("VCO_CELL_NAME", "cml_vco_delay")
layout.read(f"/work/{cell}.gds")
view = lay.LayoutView()
view.show_layout(layout, True)
view.max_hier()
view.zoom_fit()
view.save_image(f"/work/{cell}-layout.png", 1800, 1800)
assert Path(f"/work/{cell}-layout.png").stat().st_size > 10000
