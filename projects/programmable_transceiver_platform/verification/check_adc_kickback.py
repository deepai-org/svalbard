"""Check polarity and transient charge excursion in matched clamped-input runs."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
parser=argparse.ArgumentParser();parser.add_argument('--fine',action='store_true');args=parser.parse_args()
tag='adc-kickback-fine' if args.fine else 'adc-kickback'
W=R/('scratch/transceiver-'+tag)
source=P/'evidence'/(tag+'-clamped.json');d=json.loads(source.read_text());rows=[]
for c in d['cases']:
 for ext,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(c['name']+ext)).read_bytes()).hexdigest()==h
for r in d['results']:
 diff=r['differential_v'];a=np.loadtxt(W/f'd{diff:g}_clk1.dat',skiprows=1);b=np.loadtxt(W/f'd{diff:g}_clk0.dat',skiprows=1)
 t=np.r_[2e-9,a[(a[:,0]>2e-9)&(a[:,0]<4.9e-9),0],4.9e-9]
 current=np.interp(t,a[:,0],a[:,1]-a[:,2])-np.interp(t,b[:,0],b[:,1]-b[:,2])
 charge=np.r_[0,np.cumsum((current[1:]+current[:-1])*.5*np.diff(t))]
 assert np.isclose(charge[-1],r['differential_source_charge_c'],rtol=1e-5,atol=1e-25)
 assert np.sign(r['output_difference_v'])==np.sign(diff)
 rows.append(dict(differential_v=diff,net_differential_charge_c=float(charge[-1]),maximum_absolute_cumulative_charge_c=float(np.max(abs(charge)))))
for i,j in [(0,3),(1,2)]:
 assert np.isclose(rows[i]['net_differential_charge_c'],-rows[j]['net_differential_charge_c'],rtol=1e-6,atol=1e-25)
report=dict(status='clamped_charge_controls_pass',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),results=rows,limitations=d['limitations']+['Maximum cumulative charge depends on integration start; do not treat final net charge as maximum disturbance.'])
(P/'evidence'/(tag+'-excursion.json')).write_text(json.dumps(report,indent=2)+'\n')
print(rows)
