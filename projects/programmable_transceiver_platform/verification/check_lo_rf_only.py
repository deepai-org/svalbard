"""RF-only scope/provenance gate and short-window clock diagnostics."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-lo-rf-only';B=W.with_name(W.name+'-prepared')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def excursions(y,low=.66,high=2.64):
    armed=False;count=0
    for v in y:
        if v<=low:armed=True
        elif v>=high and armed:count+=1;armed=False
    return count
assert excursions([0,3.3,0,3.3])==2
assert excursions([1.64,1.66]*100)==0
assert excursions([0,3.3,3.3,3.3])==1
m=json.loads((B/'manifest.json').read_text());s=(B/'latest.spice').read_text()
assert sha(B/'latest.spice')==m['artifacts_sha256']['latest.spice']
rf=[l.split()[0] for l in s.splitlines() if l.startswith('X') and ' pt_lo_rf_isolated' in l]
assert rf==['XBIP','XBIN','XBQP','XBQN']
assert [l for l in s.splitlines() if l.startswith('X') and ' pt_lo_buffer' in l]==['XFB FBG FB VDIV 0 pt_lo_buffer S=1']
assert '.include /screen/lo_buffer.spice' in s
original=(R/'scratch/transceiver-latest-rf-loop-selective/latest.spice').read_text()
# Remove only the separately named subcircuit, retaining original include.
start=s.index('\n* Candidate two-stage',s.index('.include /screen/lo_buffer.spice'))
end=s.index('.ends pt_lo_rf_isolated',start)+len('.ends pt_lo_rf_isolated')
restored=s[:start]+s[end:]
for name in rf:
    lines=[l for l in restored.splitlines() if l.startswith(name+' ')];assert len(lines)==1
    restored=restored.replace(lines[0],lines[0].replace('pt_lo_rf_isolated','pt_lo_buffer'))
restored=restored.replace('tran 2p 1001n 0 2p uic','tran 2p 8001n 0 2p uic')
assert restored==original
if not (W/'result.json').exists():
    print('Scope controls pass; no terminal result, no waveform scoring.')
else:
    r=json.loads((W/'result.json').read_text());assert r['returncode']==0 and not r['timed_out']
    assert r['sources_before']==r['sources_after']
    for ext,h in r['artifacts_sha256'].items():assert sha(W/('latest'+ext))==h
    assert sha(W/'latest.spice')==sha(B/'latest.spice')
    with (W/'latest.dat').open() as f:h=f.readline().lower().split()
    a=np.loadtxt(W/'latest.dat',skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
    assert abs(a[-1,0]-1001e-9)<1e-15
    late=a[(a[:,0]>=800e-9)&(a[:,0]<=1000e-9)]
    def v(n):return late[:,h.index(n)]
    nodes={}
    for n in ('v(oip)','v(oin)','v(oqp)','v(oqn)','v(fb)','v(ref)'):
        y=v(n);nodes[n]=dict(minimum_v=float(y.min()),maximum_v=float(y.max()),
            rises_1v65=int(np.sum((y[:-1]<1.65)&(y[1:]>=1.65))),rail_excursions=excursions(y))
    diff=v('v(p)')-v('v(n)')
    report=dict(completed=True,qualified=False,window_ns=[800,1000],nodes=nodes,
        oscillator_differential_peak_to_peak_v=float(np.ptp(diff)),control_range_v=[float(v('v(ctrl)').min()),float(v('v(ctrl)').max())],
        waveform_sha256=sha(W/'latest.dat'),checker_sha256=sha(Path(__file__)),
        limitations=['Excursion thresholds are diagnostics, not proven mixer/PLL specifications.','Short seeded run cannot establish lock, cold-start or phase noise.'])
    (P/'evidence/lo-rf-only.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
