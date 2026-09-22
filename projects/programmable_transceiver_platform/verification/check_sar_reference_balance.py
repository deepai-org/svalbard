"""Gate reference-current interpretation on diagnostic reproduction."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-sar-reference-balance';B=W.with_name(W.name+'-prepared')
D=R/'scratch/transceiver-sar-bottom-plates';DB=D.with_name(D.name+'-prepared')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(path):
    with path.open() as f:h=f.readline().lower().split()
    a=np.loadtxt(path,skiprows=1)
    assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
    assert abs(a[-1,0]-209.9e-9)<1e-15
    return h,a
m=json.loads((B/'manifest.json').read_text());assert sha(DB/'manifest.json')==m['baseline_preparation_sha256']
assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
s=(B/'baseline.spice').read_text();extra=' '+' '.join(m['probes'])
original=s.replace('save all'+extra+'\n','')
line=next(l for l in original.splitlines() if l.startswith('wrdata '));assert line.endswith(extra)
original=original.replace(line,line[:-len(extra)]).replace('VSENSEH VH CDACH 0\nVSENSEL VL CDACL 0\n','').replace('XD HP HN CDACH CDACL ','XD HP HN VH VL ')
assert original==(DB/'baseline.spice').read_text()
if not (W/'result.json').exists():
    print('Exact scope checks pass; terminal simulation result pending.')
else:
    r=json.loads((W/'result.json').read_text());assert r['returncode']==0 and not r['timed_out']
    assert r['sources_before']==r['sources_after']==json.loads((D/'result.json').read_text())['sources_before']
    assert sha(W/'baseline.spice')==sha(B/'baseline.spice')
    for ext,hsh in r['artifacts_sha256'].items():assert sha(W/('baseline'+ext))==hsh
    parent=json.loads((P/'evidence/sar-all-bottom-plates.json').read_text());assert sha(D/'baseline.dat')==parent['waveform_sha256']
    h,a=load(W/'baseline.dat');dh,b=load(D/'baseline.dat')
    t=a[:,0];bt=b[:,0];lo,hi=np.array(m['reproduction']['window_ns'])*1e-9
    grid=np.unique(np.r_[lo,hi,t[(t>lo)&(t<hi)],bt[(bt>lo)&(bt<hi)]])
    def interp(data,header,node,grid):return np.interp(grid,data[:,0],data[:,header.index(node)])
    errors={node:float(np.max(abs(interp(a,h,f'v({node})',grid)-interp(b,dh,f'v({node})',grid)))) for node in ('hp','hn','vh','vl')}
    times=np.array([hold+2.4+5*j for hold in (70,120,170) for j in range(8)])*1e-9
    actual=interp(a,h,'v(qp)',times)-interp(a,h,'v(qn)',times)
    expected=interp(b,dh,'v(qp)',times)-interp(b,dh,'v(qn)',times)
    decisions=bool(np.all(abs(actual)>2.97) and np.all(abs(expected)>2.97) and np.array_equal(np.sign(actual),np.sign(expected)))
    sense_error=max(float(np.max(abs(a[:,h.index(f'v({rail})')]-a[:,h.index(f'v({pin})')]))) for rail,pin in [('vh','cdach'),('vl','cdacl')])
    assert sense_error<1e-12
    passed=max(errors.values())<=m['reproduction']['analog_maximum_error_v'] and decisions
    report=dict(completed=True,reproduction_pass=passed,analog_errors_v=errors,all_decisions_match=decisions,sense_voltage_error_v=sense_error,
        waveform_sha256=sha(W/'baseline.dat'),preparation_sha256=sha(B/'manifest.json'),result_sha256=sha(W/'result.json'),checker_sha256=sha(Path(__file__)),
        limitations=['Reproduction gate only; does not validate current balance or identify missing displacement terms.'])
    (P/'evidence/sar-reference-balance.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
