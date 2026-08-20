#!/usr/bin/env python3
from pathlib import Path

import klayout.db as db
import klayout.lay as lay

layout = db.Layout()
layout.read("/work/serializer_tx.gds")
view = lay.LayoutView()
view.show_layout(layout, True)
view.max_hier()
view.zoom_fit()
view.save_image("/work/layout-integrated-serializer-tx.png", 1800, 2400)
assert Path("/work/layout-integrated-serializer-tx.png").stat().st_size > 10_000
