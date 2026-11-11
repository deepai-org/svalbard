#!/usr/bin/env python3
"""Long-gate MOS decap filler cells for the gf180mcu_fd_sc_mcu7t5v0 rows (pt_decap50_4/_8/_16).

Why not thin oxide in the rows (first attempt, kept as THIN=True): KLayout DRC of 3.3 V devices abutted
to library cells fails DV.9 (3.3 V and 5 V PMOS may not share an NWELL; the row NWELL is continuous)
and DV.3/DV.6/DV.7/DV.8 (the library cells' DUALGATE overhangs 0.28 um into the neighbour and
row-below cell). A thin-oxide NMOS that clears those margins is so narrow that the cell is no
denser than the 5 V version. These cells therefore use the library's own proven 5 V devices
(nfet_05v0/pfet_05v0, DUALGATE + V5_XTOR exactly as fillcap) and gain density with 1 um gate
fingers sharing their diffusion contact columns (fillcap: two separate 1 um devices per 8 sites).
A single long gate per device was also tried: its channel resistance (ESR ~47 kohm per 16-site cell)
removes half the capacitance by 100 MHz, inside the 20-200 MHz PDN band.

Run with KLayout's Python (klayout.db), e.g. inside the pinned analog image:
    python3 gen_decap.py OUTDIR
Writes OUTDIR/pt_decap50.gds (cells pt_decap50_4/_8/_16/_32/_64 = 4..64 sites of 0.56 um, height 3.92 um),
OUTDIR/pt_decap50.spice (LVS reference) and OUTDIR/geometry.json.

Topology (as the library fillcap cells, cross-coupled so no gate sits directly on a rail):
    MN  fingers G=nh, diffusion VSS (rightmost column nl), B=VPW   nfet_05v0 W 0.82 um L 1.0 um
    MP  fingers G=nl, diffusion VDD (leftmost column nh),  B=VNW   pfet_05v0 W 1.22 um L 1.0 um
At power-up MP pulls nh to VDD and MN pulls nl to VSS; both gates are then inverted MOS capacitors
between the rails. Rows, rails (Metal1 VDD/VSS 0.6 um), well/implant boundaries and the cell
boundary match the library (fillcap_8), so the cells abut any library cell. No DUALGATE and no
V5_XTOR in the THIN variant; the default carries both, like every library cell.
"""
import json, sys
try:
    import klayout.db as db
except ImportError:   # --views needs no KLayout
    db = None

SITE, H = 560, 3920
L = {  # gf180mcu klayout layer map (tech/gf180mcu.lyp)
    'NWELL': (21, 0), 'LVPWELL': (204, 0), 'COMP': (22, 0), 'POLY2': (30, 0), 'NPLUS': (32, 0), 'PPLUS': (31, 0),
    'CONTACT': (33, 0), 'METAL1': (34, 0), 'METAL1_LABEL': (34, 10), 'NWELL_LABEL': (21, 10),
    'LVPWELL_LABEL': (204, 10), 'PR_BNDRY': (0, 0), 'DUALGATE': (55, 0), 'V5_XTOR': (112, 1)}
CO = 220
THIN = False
PFX = 'pt_decap33' if THIN else 'pt_decap50'


def build(ly, nsites):
    W = nsites * SITE
    c = ly.create_cell(f'{PFX}_{nsites}')
    li = {k: ly.layer(*v) for k, v in L.items()}
    box = lambda k, x1, y1, x2, y2: c.shapes(li[k]).insert(db.Box(x1, y1, x2, y2))
    box('PR_BNDRY', 0, 0, W, H)
    if not THIN:
        box('DUALGATE', -280, -280, W + 280, 4200)
        box('V5_XTOR', 0, 0, W, H)
    box('NWELL', -430, 1760, W + 430, 4350)
    box('LVPWELL', -430, -430, W + 430, 1760)
    box('NPLUS', -200, -200, W + 200, 1760)
    box('PPLUS', -200, 1760, W + 200, 4120)
    # active
    box('COMP', 180, 340, W - 180, 1160)          # NMOS
    box('COMP', 180, 2360, W - 180, 3580)         # PMOS
    # Fingers: L = 1.0 um gates (the fillcap gate length; a single long gate was tried and loses its
    # capacitance above ~30 MHz to channel resistance), sharing diffusion contact columns.
    # Column k at x = 250 + k * PITCH; gate k between columns k and k+1.
    LG, PITCH = 1000, 1000 + 2 * 150 + CO
    ncol = (W - 180 - 70 - CO - 250) // PITCH + 1
    cols = [250 + k * PITCH for k in range(ncol)]
    span = cols[-1] + CO + 70 + 180               # right end of COMP actually used
    gates = [(x + CO + 150, x + CO + 150 + LG) for x in cols[:-1]]
    for g0, g1 in gates:
        box('POLY2', g0, 120, g1, 1620)           # MN finger (+ bar overlap)
        box('POLY2', g0, 1875, g1, 3800)          # MP finger
    # No poly bar between fingers (field poly would face the COMP edge closer than PL.5a/b_MV 0.3 um):
    # each finger keeps its own contact pad, as in fillcap, and Metal1 joins the gate contacts.
    for x in cols:
        box('CONTACT', x, 640, x + CO, 640 + CO)
        for y in (2580, 3070):
            box('CONTACT', x, y, x + CO, y + CO)
    # gate contacts on each finger's pad (centre)
    xs = [(g0 + g1) // 2 - CO // 2 for g0, g1 in gates]
    for x in xs:
        box('CONTACT', x, 1330, x + CO, 1330 + CO)   # nh
        box('CONTACT', x, 1965, x + CO, 1965 + CO)   # nl
    # Metal1 (0.34 um over contacts: 0.06 um overlap on every edge, CO.6a/b)
    box('METAL1', 0, -300, W, 300)                # VSS rail
    box('METAL1', 0, 3620, W, 4220)               # VDD rail
    xl, xr = cols[0], cols[-1]
    for x in cols[:-1]:                           # MN columns except the rightmost -> VSS
        box('METAL1', x - 60, 300, x + CO + 60, 920)
    for x in cols[1:]:                            # MP columns except the leftmost -> VDD
        box('METAL1', x - 60, 2520, x + CO + 60, 3620)
    box('METAL1', xl - 60, 1270, xl + CO + 60, 3350)          # nh: MP leftmost column ...
    box('METAL1', xl - 60, 1270, xs[-1] + CO + 60, 1610)      # ... to the MN gate contacts
    box('METAL1', xr - 60, 580, xr + CO + 60, 2245)           # nl: MN rightmost column ...
    box('METAL1', xs[0] - 60, 1905, xr + CO + 60, 2245)       # ... to the MP gate contacts
    for lab, k, y in (('VDD', 'METAL1_LABEL', 3910), ('VSS', 'METAL1_LABEL', 10)):
        c.shapes(li[k]).insert(db.Text(lab, db.Trans(W // 2, y)))
    c.shapes(li['NWELL_LABEL']).insert(db.Text('VNW', db.Trans(345, 3920)))
    c.shapes(li['LVPWELL_LABEL']).insert(db.Text('VPW', db.Trans(340, -85)))
    nf = len(gates)
    return c, dict(width_um=W / 1000, height_um=H / 1000, fingers=nf, nmos=dict(w_um=0.82, l_um=LG / 1000),
                   pmos=dict(w_um=1.22, l_um=LG / 1000), gate_area_um2=round((0.82 + 1.22) * nf * LG / 1000, 4),
                   area_um2=W * H / 1e6)


def main(out):
    ly = db.Layout(); ly.dbu = 0.001
    geo, sp = {}, []
    for n in (4, 8, 16, 32, 64):
        c, g = build(ly, n)
        geo[c.name] = g
        l, nf = g['nmos']['l_um'], g['fingers']
        dn, dp = ('nfet_03v3', 'pfet_03v3') if THIN else ('nfet_05v0', 'pfet_05v0')
        # KLayout gf180mcu LVS form (calibrated on the library fillcap_8: M cards, ports SUB VDD VSS,
        # run_lvs.py --top_lvl_pins; the cell has no well taps, so the p-well is SUB and the n-well floats
        # until a tap cell joins it, exactly as for fillcap).
        # finger k: NMOS between column k (VSS, or nl for the last column) and k+1; PMOS between
        # column k (nh for k = 0, else VDD) and k+1
        lines = [f'.subckt {c.name} SUB VDD VSS']
        for k in range(nf):
            nd = 'nl' if k + 1 == nf else 'VSS'
            ps = 'nh' if k == 0 else 'VDD'
            lines.append(f'MMN{k} {nd} nh VSS SUB {dn} W={0.82e-6:.3e} L={l * 1e-6:.4e}')
            lines.append(f'MMP{k} {ps} nl VDD nw {dp} W={1.22e-6:.3e} L={l * 1e-6:.4e}')
        sp.append('\n'.join(lines) + '\n.ends\n')
    ly.write(f'{out}/{PFX}.gds')
    open(f'{out}/{PFX}.spice', 'w').write(f'* {PFX} LVS reference (verification/digital_hardening/decap/gen_decap.py)\n' + '\n'.join(sp))
    json.dump(geo, open(f'{out}/geometry.json', 'w'), indent=1)
    print(json.dumps(geo, indent=1))





# ---------------------------------------------------------------------------------------------
# LEF and Liberty views (plain Python; no KLayout needed): python3 gen_decap.py --views OUTDIR
def views(out):
    geo = json.load(open(f'{out}/geometry.json'))
    lef = ['VERSION 5.7 ;', 'BUSBITCHARS "[]" ;', 'DIVIDERCHAR "/" ;', '']
    lib = ['/* pt_decap50 filler decap cells (verification/digital_hardening/decap/gen_decap.py). No signal pins and',
           ' * no timing; area and power pins only, so STA/power tools accept them in the netlist. */',
           'library(pt_decap50) {', '  delay_model : table_lookup ;', '  time_unit : 1ns ;', '  voltage_unit : 1V ;',
           '  current_unit : 1mA ;', '  capacitive_load_unit(1, pf) ;', '  leakage_power_unit : 1uW ;',
           '  nom_process : 1 ;', '  nom_temperature : 25 ;', '  nom_voltage : 3.3 ;',
           '  voltage_map(VDD, 3.3) ;', '  voltage_map(VNW, 3.3) ;', '  voltage_map(VSS, 0) ;', '  voltage_map(VPW, 0) ;',
           '  operating_conditions(typical) { process : 1 ; temperature : 25 ; voltage : 3.3 ; }',
           '  default_operating_conditions : typical ;']
    for name, g in sorted(geo.items(), key=lambda kv: kv[1]['width_um']):
        W = g['width_um']
        lef += [f'MACRO {name}', '  CLASS CORE SPACER ;', f'  FOREIGN {name} ;', '  ORIGIN 0.000 0.000 ;',
                f'  SIZE {W:.3f} BY 3.920 ;', '  SYMMETRY X Y ;', '  SITE GF018hv5v_mcu_sc7 ;',
                '  PIN VDD', '    DIRECTION INOUT ;', '    USE POWER ;', '    SHAPE ABUTMENT ;', '    PORT',
                '      LAYER Metal1 ;', f'        RECT 0.000 3.620 {W:.3f} 4.220 ;', '    END', '  END VDD',
                '  PIN VNW', '    DIRECTION INOUT ;', '    USE POWER ;', '    PORT', '      LAYER Nwell ;',
                f'        RECT -0.430 1.760 {W + 0.43:.3f} 4.350 ;', '    END', '  END VNW',
                '  PIN VPW', '    DIRECTION INOUT ;', '    USE GROUND ;', '    PORT', '      LAYER Pwell ;',
                f'        RECT -0.430 -0.430 {W + 0.43:.3f} 1.760 ;', '    END', '  END VPW',
                '  PIN VSS', '    DIRECTION INOUT ;', '    USE GROUND ;', '    SHAPE ABUTMENT ;', '    PORT',
                '      LAYER Metal1 ;', f'        RECT 0.000 -0.300 {W:.3f} 0.300 ;', '    END', '  END VSS',
                '  OBS', '      LAYER Metal1 ;', f'        RECT 0.190 0.300 {W - 0.19:.3f} 3.620 ;', '  END',
                f'END {name}', '']
        lib += [f'  cell({name}) {{', f'    area : {g["area_um2"]:.4f} ;', '    dont_touch : true ;',
                '    dont_use : true ;', '    is_filler_cell : true ;', '    cell_leakage_power : 0 ;',
                '    pg_pin(VDD) { pg_type : primary_power ; voltage_name : VDD ; }',
                '    pg_pin(VSS) { pg_type : primary_ground ; voltage_name : VSS ; }',
                '    pg_pin(VNW) { pg_type : nwell ; voltage_name : VNW ; }',
                '    pg_pin(VPW) { pg_type : pwell ; voltage_name : VPW ; }', '  }']
    lef.append('END LIBRARY')
    lib.append('}')
    open(f'{out}/pt_decap50.lef', 'w').write('\n'.join(lef) + '\n')
    open(f'{out}/pt_decap50.lib', 'w').write('\n'.join(lib) + '\n')


if __name__ == '__main__':
    if sys.argv[1] == '--views':
        views(sys.argv[2])
    else:
        main(sys.argv[1])
