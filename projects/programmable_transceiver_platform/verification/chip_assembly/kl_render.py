# KLayout batch render of the assembled chip to a PNG whose pixels map linearly onto the die (for fp_png overlays).
#   klayout -b -rd gds=/work/pt_chip_top.gds -rd out=/work/chip-bg.png -rd w=1400 -r kl_render.py
import klayout.db as db
import klayout.lay as lay
W = int(w)
DIE = (3932.0, 5122.0)
H = int(round(W*DIE[1]/DIE[0]))
view = lay.LayoutView()
view.set_config('background-color', '#ffffff')
view.set_config('grid-visible', 'false')
view.set_config('text-visible', 'false')
idx = view.load_layout(gds, True)
lyp = '/foss/pdks/gf180mcuD/libs.tech/klayout/tech/gf180mcu.lyp'
try:
    view.load_layer_props(lyp)
except Exception as e:      # noqa: BLE001
    print('no lyp', e)
view.max_hier()
view.zoom_box(db.DBox(0, 0, DIE[0], DIE[1]))
view.save_image(out, W, H)
print('RENDER', W, H)
