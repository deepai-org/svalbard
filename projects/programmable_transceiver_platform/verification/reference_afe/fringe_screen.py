"""2-D electrostatic sensitivity screen for stacked metal strips, not chip PEX.
Usage: python fringe_screen.py SUBMITTED.gds
Homogeneous oxide, infinite extrusion, rectangular conductors; scipy and KLayout.
"""
import json,sys,hashlib
from pathlib import Path
import klayout.db as k
import numpy as np
from scipy.sparse import diags,kron,eye
from scipy.sparse.linalg import spsolve
layout_path=Path(sys.argv[1]);layout=k.Layout();layout.read(str(layout_path))
cell=layout.cell('lib_unit_cap_8192x');strip_geometry={}
for layer in [36,42,46]:
 cross=(k.Region(cell.begin_shapes_rec(layout.layer(layer,0)))&k.Region(k.Box(-1000,16000,200000,16001))).merged()
 boxes=sorted([p.bbox() for p in cross.each()],key=lambda b:b.left)
 widths=np.asarray([b.width()*layout.dbu for b in boxes]);lefts=np.asarray([b.left*layout.dbu for b in boxes])
 assert np.allclose(widths,.5) and np.allclose(np.diff(lefts),1.5)
 strip_geometry[str(layer)]=dict(strip_count=len(boxes),width_um=float(widths[0]),pitch_um=float(lefts[1]-lefts[0]))
EPS=8.8541878128e-12*4

def solve(width=.5,gap=.9,thickness=.55,step=.025,margin=3.,parallel=False,pitch=None,include_m2=False,lateral=False):
 # Coordinates in um; capacitance/length is independent of coordinate units.
 nx=round((2*width+gap+2*margin if lateral else (pitch if pitch else width+2*margin))/step);ny=round((thickness+2*margin if lateral else gap+2*thickness+2*margin)/step)
 x=(np.arange(nx)+.5)*step-nx*step/2
 y=(np.arange(ny)+.5)*step-ny*step/2
 xx,yy=np.meshgrid(x,y)
 if parallel:
  high=np.zeros((ny,nx),bool);low=high.copy();high[-1]=True;low[0]=True
 else:
  high=(abs(xx)<width/2-1e-9)&(yy>=gap/2)&(yy<gap/2+thickness)
  low=(abs(xx)<width/2-1e-9)&(yy<=-gap/2)&(yy>-gap/2-thickness)
 if lateral:
  high=(xx>=-gap/2-width)&(xx<-gap/2)&(abs(yy)<thickness/2)
  low=(xx>=gap/2)&(xx<gap/2+width)&(abs(yy)<thickness/2)
 if include_m2:
  if parallel or pitch is None:raise ValueError('M2 screen uses periodic strips')
  m2_top=-gap/2-thickness-gap
  low|=(abs(xx)<width/2-1e-9)&(yy<=m2_top)&(yy>m2_top-thickness)
 fixed=high|low
 if pitch is None:fixed[0]=True;fixed[-1]=True
 if not parallel and pitch is None:fixed[:,0]=True;fixed[:,-1]=True
 values=np.zeros((ny,nx));values[high]=1. if lateral else .5;values[low]=0. if lateral else -.5
 tx=diags([-np.ones(nx-1),2*np.ones(nx),-np.ones(nx-1)],[-1,0,1],format='lil')
 if parallel or pitch is not None:tx[0,-1]=-1;tx[-1,0]=-1
 ty=diags([-np.ones(ny-1),2*np.ones(ny),-np.ones(ny-1)],[-1,0,1],format='lil')
 if pitch is not None:ty[0,0]=1;ty[-1,-1]=1
 ty=ty.tocsr()
 matrix=(kron(eye(ny),tx.tocsr())+kron(ty,eye(nx))).tocsr()
 unknown=np.flatnonzero(~fixed.ravel());known=np.flatnonzero(fixed.ravel())
 rhs=-matrix[unknown][:,known]@values.ravel()[known]
 solution=spsolve(matrix[unknown][:,unknown],rhs)
 values.ravel()[unknown]=solution
 flux=matrix@values.ravel()
 charge_high=float(np.sum(flux[high.ravel()]))*EPS
 charge_low=float(np.sum(flux[low.ravel()]))*EPS
 # Outer Dirichlet boundary contributes only to parallel plate charge formula.
 if parallel:
  charge_high=float(np.sum(values[-1]-values[-2]))*EPS
  charge_low=float(np.sum(values[0]-values[1]))*EPS
 residual=float(np.max(abs((matrix@values.ravel())[unknown])))
 return dict(width_um=width,gap_um=gap,thickness_um=thickness,step_um=step,margin_um=margin,
  lateral=lateral,mutual_capacitance_ff_per_um=-charge_low*1e9 if lateral else None,
  pitch_um=pitch,include_m2=include_m2,nodes=nx*ny,capacitance_ff_per_um=charge_high*1e9,charge_balance_relative=abs(charge_high+charge_low)/charge_high,
  laplace_max_residual=residual,plate_only_ff_per_um=EPS*width/gap*1e9,
  parallel_expected_ff_per_um=EPS*(nx*step)/((ny-1)*step)*1e9 if parallel else None)

if '--lateral-only' in sys.argv:
 rows=[solve(width=.28,gap=.5,step=h,margin=m,lateral=True) for h,m in [(.02,3.),(.01,3.),(.02,6.)]]
 assert all(r['mutual_capacitance_ff_per_um']>0 and r['laplace_max_residual']<1e-10 for r in rows)
 print(json.dumps(dict(cases=rows,scope='Assigned homogeneous oxide4,metal0.55um;0.28um wires separated0.5um, matching B0/B2 parent routing cross section. Infinite extrusion; grounded box, no nearby metal or dielectric interfaces. Mutual capacitance from grounded wire charge under1V excitation, not total driven charge.'),indent=2));sys.exit()
control=solve(parallel=True)
assert abs(control['capacitance_ff_per_um']/control['parallel_expected_ff_per_um']-1)<1e-9
rows=[solve(step=h) for h in [.05,.025,.0125]]
rows += [solve(step=.025,pitch=1.5),solve(step=.0125,pitch=1.5),solve(step=.025,pitch=1.5,margin=6),solve(step=.025,margin=6),solve(step=.025,gap=1.15),solve(step=.025,width=1.5)]
rows += [solve(step=h,pitch=1.5,include_m2=True) for h in [.025,.0125]]
rows += [solve(step=.025,pitch=1.5,include_m2=True,margin=6),solve(step=.025,pitch=1.5,include_m2=True,gap=1.15)]
assert all(r['charge_balance_relative']<1e-8 and r['laplace_max_residual']<1e-10 for r in rows)
print(json.dumps(dict(source_sha256=hashlib.sha256(layout_path.read_bytes()).hexdigest(),cross_section_cell=cell.name,cross_section_y_um=16,layout_strip_geometry=strip_geometry,parallel_plate_control=control,cases=rows,
 interpretation='Isolated M3/M4 and periodic M2/M3/M4 strips: fringes and metal thickness change capacitance per length; not actual array bit weights.',
 assumptions=['Oxide relative permittivity4; metal thickness0.55um from public stack simulation tables.',
 '0.9um gap is an equivalent spacing inferred from0.0394fF/um2 plate density;1.15um is a separate geometric sensitivity, not a resolved interpretation of IMD thickness.',
 'Widths0.5/1.5um represent layout strip scales; M2 included in tagged periodic cases, tied to M3 with the same assumed inter-metal gap. Actual finite lengths, different neighboring-bit potentials, vias, routing, trapezoidal sidewalls and nonuniform dielectric omitted.',
 'Isolated-strip outer boundaries grounded; periodic-strip vertical boundaries have zero normal flux. Electrodes+/-0.5V. Boundary-distance and mesh refinements reported.',
 'This deterministic electrostatic exercise gives no statistical process bounds or calibrated full capacitance matrix.']),indent=2))
