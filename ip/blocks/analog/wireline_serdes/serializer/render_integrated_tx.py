#!/usr/bin/env python3
from pathlib import Path
import os

import klayout.db as db
import klayout.lay as lay

layout = db.Layout()
gds_path = os.environ.get("INTEGRATED_TX_GDS", "/work/serializer_tx.gds")
render_path = os.environ.get(
    "INTEGRATED_TX_RENDER", "/work/layout-integrated-serializer-tx.png"
)
layout.read(gds_path)
view = lay.LayoutView()
view.show_layout(layout, True)
view.max_hier()
view.zoom_fit()
view.save_image(render_path, 1800, 2400)
assert Path(render_path).stat().st_size > 10_000
