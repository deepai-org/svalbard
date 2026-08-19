#!/usr/bin/env python3
from pathlib import Path
import klayout.db as db
import klayout.lay as lay

layout = db.Layout()
layout.read("/work/vco_selector_tree.gds")
view = lay.LayoutView()
view.show_layout(layout, True)
view.max_hier()
view.zoom_fit()
view.save_image("/work/vco-selector-tree-layout.png", 2800, 1500)
assert Path("/work/vco-selector-tree-layout.png").stat().st_size > 20_000
