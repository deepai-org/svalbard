# Render a chip GDS: klayout -zz -rd gds=<chip.gds> -rd out=<png> -r render_gds.py
import pya
v = pya.LayoutView(); v.set_config("background-color", "#ffffff"); v.set_config("grid-visible", "false")
v.load_layout(gds, True); v.max_hier(); v.zoom_fit()
v.save_image(out, 1600, 2080)
print("ok", out)
