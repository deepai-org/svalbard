#!/usr/bin/env python3
from pathlib import Path

import klayout.db as db
import klayout.lay as lay

layout = db.Layout()
layout.read("/work/cml_serializer_2to1.gds")
view = lay.LayoutView()
view.show_layout(layout, True)
view.max_hier()
view.zoom_fit()
view.save_image("/work/layout-serializer.png", 1800, 1800)
assert Path("/work/layout-serializer.png").stat().st_size > 10_000
