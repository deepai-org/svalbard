"""Measure a reset-state two-port admittance matrix with independent AC drives."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-adc-top-load-matrix';W.mkdir()
base=(P/'analog/adc/top_load.spice').read_text()
for name,pdrive,ndrive in [('positive','1','0'),('negative','0','1')]:
 s=base.replace('DC 1.65 AC .5\n',f'DC 1.65 AC {pdrive}\n').replace('DC 1.65 AC .5 180',f'DC 1.65 AC {ndrive}').replace('/work/load.dat',f'/work/{name}.dat')
 assert s!=base
 (W/(name+'.spice')).write_text(s)
image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
files=[P/'analog/adc/top_load.spice',P/'analog/adc/comparator.spice',R/'ip/blocks/analog/wifi_80211b/rf_if_transmission_gate/rf_if_transmission_gate.spice']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={str(p.relative_to(R)):sha(p) for p in files}
subprocess.run(['docker','run','--rm','--platform','linux/arm64','--network','none','--cpus','1','--memory','2g','--entrypoint','/bin/bash','-v',f'{P}/analog:/screen:ro','-v',f'{R}/ip/blocks/analog/wifi_80211b:/wifi:ro','-v',f'{W}:/work','--workdir','/work',image,'-lc','for deck in *.spice; do ngspice -b "$deck" > "${deck%.spice}.log" 2>&1 || exit 1; done'],check=True,capture_output=True)
assert before=={str(p.relative_to(R)):sha(p) for p in files}
arrays=[];artifacts={}
for name in ['positive','negative']:
 log=(W/(name+'.log')).read_text().lower()
 assert 'ngspice-46 done' in log and not any(x in log for x in ['warning','error','aborted'])
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape==(10,7) and np.isfinite(a).all();arrays.append(a)
 for ext in ['.spice','.log','.dat']:artifacts[name+ext]=sha(W/(name+ext))
a,b=arrays;assert np.array_equal(a[:,0],b[:,0])
y=np.empty((len(a),2,2),complex)
y[:,0,0]=-(a[:,1]+1j*a[:,2]);y[:,1,0]=-(a[:,3]+1j*a[:,4])
y[:,0,1]=-(b[:,1]+1j*b[:,2]);y[:,1,1]=-(b[:,3]+1j*b[:,4])
# Independent column drives must reproduce the earlier differential-drive fixture.
prior_path=R/'scratch/transceiver-adc-top-load/load.dat'
prior=np.loadtxt(prior_path,skiprows=1)
assert np.array_equal(a[:,0],prior[:,0])
measured=np.column_stack([-(prior[:,1]+1j*prior[:,2]),-(prior[:,3]+1j*prior[:,4])])
reconstructed=y@np.array([.5,-.5])
error=float(np.max(abs(reconstructed-measured)))
assert np.allclose(reconstructed,measured,rtol=1e-6,atol=1e-13)
c=y.imag/(2*np.pi*a[:,0,None,None])
report=dict(status='reset_state_admittance_matrix_only',image=image,source_sha256=before,artifacts_sha256=artifacts,prior_waveform_sha256=sha(prior_path),script_sha256=sha(Path(__file__)),frequencies_hz=a[:,0].tolist(),capacitance_matrix_ff=(c*1e15).tolist(),conductance_matrix_s=y.real.tolist(),differential_reconstruction_max_error_a=error,limitations=['Susceptance divided by frequency is an effective capacitance matrix at this bias/state.', 'Internal active-device dynamics may make the matrix frequency-dependent; no passive equivalent guaranteed.', 'Comparator evaluation, clock injection, process spread and extracted parasitics are absent.'])
(P/'evidence/adc-top-load-matrix.json').write_text(json.dumps(report,indent=2)+'\n')
print('1MHz effective capacitance matrix fF',c[0]*1e15,'reconstruction error A',error)
