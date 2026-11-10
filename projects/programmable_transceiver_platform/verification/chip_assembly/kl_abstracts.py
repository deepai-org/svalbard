# KLayout batch script (run inside the pinned KLayout image).
#   klayout -b -rd spec=/work/masters.json -rd out=/work -r kl_abstracts.py
# For every master: true GDS bounds (all layers incl. straps/pins), per-layer
# extents, labelled terminals resolved to the metal shape under each label,
# and a LEF abstract (CLASS BLOCK, SIZE = full GDS bbox, OBS = per-layer bbox).
import json
import klayout.db as db

METAL = {34: 'Metal1', 36: 'Metal2', 42: 'Metal3', 46: 'Metal4', 81: 'Metal5'}
spec = json.load(open(spec))
result = {}
lef = ['VERSION 5.8 ;', 'BUSBITCHARS "[]" ;', 'DIVIDERCHAR "/" ;', 'UNITS', '  DATABASE MICRONS 1000 ;', 'END UNITS', '']
for name, (path, top) in spec.items():
    ly = db.Layout()
    ly.read(path)
    cell = ly.cell(top)
    assert cell is not None, (name, top)
    box = cell.dbbox()
    layers = {}
    regions = {}
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        r = db.Region(cell.begin_shapes_rec(li))
        if r.is_empty():
            continue
        key = f'{info.layer}/{info.datatype}'
        b = r.bbox()
        layers[key] = [b.left*ly.dbu, b.bottom*ly.dbu, b.right*ly.dbu, b.top*ly.dbu]
        if info.datatype == 0 and info.layer in METAL:
            regions[info.layer] = r.merged()
    labels = []
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        for it in cell.begin_shapes_rec(li):
            s = it.shape()
            if not s.is_text():
                continue
            p = (it.trans()*s.text.trans).disp
            entry = dict(text=s.text.string, layer=f'{info.layer}/{info.datatype}', x=p.x*ly.dbu, y=p.y*ly.dbu)
            if info.layer in regions:
                probe = db.Region(db.Box(p.x-1, p.y-1, p.x+1, p.y+1))
                hit = regions[info.layer].interacting(probe)
                if not hit.is_empty():
                    # Smallest polygon under the label is the terminal.
                    poly = min(hit.each(), key=lambda q: q.area())
                    entry['rect'] = [v*ly.dbu for v in (poly.bbox().left, poly.bbox().bottom, poly.bbox().right, poly.bbox().top)]
                    entry['metal'] = METAL[info.layer]
            labels.append(entry)
    result[name] = dict(gds=path, top=top, bbox=[box.left, box.bottom, box.right, box.top],
                        width=box.width(), height=box.height(), layers=layers, labels=labels,
                        cells=len(list(cell.called_cells()))+1)
    # LEF abstract with origin moved to the bbox lower-left corner.
    ox, oy = box.left, box.bottom
    lef += [f'MACRO {name}', '  CLASS BLOCK ;', f'  FOREIGN {top} {-ox:.3f} {-oy:.3f} ;', '  ORIGIN 0 0 ;',
            f'  SIZE {box.width():.3f} BY {box.height():.3f} ;', '  SYMMETRY X Y ;']
    seen = set()
    for lab in labels:
        if 'rect' not in lab or lab['text'] in seen:
            continue
        seen.add(lab['text'])
        x1, y1, x2, y2 = lab['rect']
        use = 'POWER' if lab['text'].upper() in ('VDD', 'VDD_WIRE_SW', 'VDD_PLL_SW', 'VISL') else \
              'GROUND' if lab['text'].upper() == 'VSS' else 'SIGNAL'
        lef += [f'  PIN {lab["text"]}', '    DIRECTION INOUT ;', f'    USE {use} ;', '    PORT',
                f'      LAYER {lab["metal"]} ;', f'        RECT {x1-ox:.3f} {y1-oy:.3f} {x2-ox:.3f} {y2-oy:.3f} ;',
                '    END', f'  END {lab["text"]}']
    lef += ['  OBS']
    for num, metal in METAL.items():
        if f'{num}/0' in layers:
            x1, y1, x2, y2 = layers[f'{num}/0']
            lef += [f'    LAYER {metal} ;', f'      RECT {x1-ox:.3f} {y1-oy:.3f} {x2-ox:.3f} {y2-oy:.3f} ;']
    lef += ['  END', f'END {name}', '']
lef += ['END LIBRARY']
open(out+'/abstracts.json', 'w').write(json.dumps(result, indent=1))
open(out+'/chip_masters.lef', 'w').write('\n'.join(lef)+'\n')
print('ABSTRACTS', len(result))
