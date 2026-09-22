"""Three-frame diagnostics gated on the complete separated-event receiver run."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--inband",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-rx-adc-separated-events-v2/separated';E=P/'evidence/rx-adc-separated-events.json'
if args.inband:
 W=R/'scratch/transceiver-rx-adc-inband/inband';E=P/'evidence/rx-adc-inband.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
audit=json.loads(E.read_text());out=dict(completed=False,status='pending',audit_sha256=sha(E),frames=[])
if audit['completed']:
 case=audit['cases'][0];assert case['case']==('inband' if args.inband else 'separated') and case['completed']
 for ext,h in case['artifacts_sha256'].items():assert sha(W/('connected'+ext))==h
 with (W/'connected.dat').open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/'connected.dat',skiprows=1);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]+1e-21>=610e-9
 v=lambda n:a[:,h.index(n)]
 def window(y,lo,hi):
  lo*=1e-9;hi*=1e-9;assert t[0]<=lo<hi<=t[-1]+1e-21
  keep=(t>lo)&(t<hi);tt=np.r_[lo,t[keep],hi];yy=np.r_[np.interp(lo,t,y),y[keep],np.interp(hi,t,y)]
  return dict(min_v=float(yy.min()),max_v=float(yy.max()),mean_v=float(np.trapezoid(yy,tt)/(hi-lo)))
 for hold in (470,520,570):
  channels=[];refs=[]
  for channel,prefix in [('i',''),('q','q_')]:
   source=window(v(f'v(f{channel}p)')-v(f'v(f{channel}n)'),hold,hold+.1)
   held=window(v(f'v(xadc.{prefix}hp)')-v(f'v(xadc.{prefix}hn)'),hold+.2,hold+.35)
   mask=(t>=(hold+39)*1e-9)&(t<=(hold+39.5)*1e-9);assert mask.any()
   bits=a[mask][:,[h.index(f'v(xadc.{prefix}d{i})') for i in range(8)]]
   levels=bool(np.all((bits<.33)|(bits>2.97)))
   channels.append(dict(channel=channel,source_turnoff=source,held_before_first_compare=held,
    held_minus_source_envelope_v=[held['min_v']-source['max_v'],held['max_v']-source['min_v']],
    captured_codes=np.unique((bits>1.65).astype(int)@2**np.arange(8)).tolist(),rail_valid_code_levels=levels,
    done=window(v(f'v(xadc.{prefix}done)'),hold+39,hold+39.5)))
  for bit in range(8):
   lo=hold+5*bit+.2;hi=hold+5*bit+.35
   refs.append(dict(bit_index=bit,window_ns=[lo,hi],high=window(v('v(xadc.vh)'),lo,hi),low=window(v('v(xadc.vl)'),lo,hi),span=window(v('v(xadc.vh)')-v('v(xadc.vl)'),lo,hi)))
  out['frames'].append(dict(hold_ns=hold,channels=channels,reference_windows=refs))
 out.update(completed=True,status='complete_run_diagnostic_measurements')
out['limitations']=['No correct-code, ENOB or bias-startup qualification; source has small excursion; three frames cannot qualify conversion.',
 'Held-minus-source envelope is not a calibrated aperture error; includes switch/CDAC initial state.',
 'Static reference target errors and dynamic span must both be assessed; no acceptance limits added after measurement.',
 'Ideal sources and seeded oscillator remain; schedule separation is not implemented phase-generation hardware.']
(P/'evidence'/('rx-adc-inband-frames.json' if args.inband else 'rx-adc-separated-frames.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
