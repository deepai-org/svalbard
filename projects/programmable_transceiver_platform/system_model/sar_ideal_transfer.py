"""Explicit ideal binary search for the actual code128 sampling convention."""
import argparse,hashlib,json,math
from pathlib import Path
P=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--rzero',action='store_true');ap.add_argument('--divider',action='store_true');ap.add_argument('--clamped',action='store_true');ap.add_argument('--sampler-double',action='store_true');args=ap.parse_args();assert sum((args.rzero,args.divider,args.clamped,args.sampler_double))<=1
def ideal(residue,span=1.):
 # 256 equal capacitors per side, complementary binary switching, one dummy.
 # Tracking code128; each code increment changes differential top voltage 2Vspan/256.
 code=0;steps=[]
 for bit in range(7,-1,-1):
  trial=code+(1<<bit);r=residue+(trial-128)*span/128
  keep=r<=0 # Exact zero ties explicitly keep; physical metastability not modeled.
  if keep:code=trial
  steps.append(dict(bit=bit,trial=trial,residue_v=r,keep=keep))
 return code,steps
# Independent closed form and exact binary-valued boundary controls.
for k in range(256):
 for offset in (.25,.75):
  x=(128-k-offset)/128
  assert ideal(x)[0]==k
for k in range(256):assert ideal((128-k)/128)[0]==k
for x in [-2.,-1.,-.4,0.,.4,1.,2.]:assert ideal(x)[0]==max(0,min(255,math.floor(128-128*x)))
e=P/'evidence'/('sar-sampler-double.json' if args.sampler_double else 'sar-reference-clamped.json' if args.clamped else 'sar-reference-divider.json' if args.divider else 'sar-reference-rzero.json' if args.rzero else 'sar-reservoir-full.json');d=json.loads(e.read_text());assert d['completed']
if args.clamped or args.sampler_double:assert d['clamps_verified']
if not (args.rzero or args.divider or args.clamped or args.sampler_double):assert d['short_reproduction_pass']
rows=[]
for variant,key in [('baseline','baseline_frames'),('sampler_double' if args.sampler_double else 'clamped' if args.clamped else 'divider' if args.divider else 'rzero' if args.rzero else 'double','frames')]:
 for i,f in enumerate(d[key]):
  target=.4 if i%2==0 else -.4;held=f['steps'][0]['preclock_residue_v']
  source_code,source_steps=ideal(target);held_code,held_steps=ideal(held)
  rows.append(dict(variant=variant,hold_ns=f['hold_ns'],input_target_v=target,measured_first_residue_v=held,actual_code=f['final_code'],ideal_source_code=source_code,source_code_difference=f['final_code']-source_code,ideal_held_anchor_code=held_code,held_anchor_code_difference=f['final_code']-held_code,ideal_held_steps=held_steps))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
out=dict(source_sha256=sha(e),topology_sha256=sha(P/'analog/adc/cdac8_mim.spice'),track_mask_sha256=sha(P/'analog/adc/sar_track_mask_strong.spice'),formula='floor(128 - 128*input_differential/reference_span), clipped 0..255; ties keep',differential_input_lsb_v=2/256,results=rows,limitations=['Nominal matched capacitors, ideal switches, constant1V span, zero comparator offset and noise.','Held anchor removes acquisition and initial reference/bottom-state errors; it is not an independent accuracy measurement.','Real input parasitic attenuation and subsequent switching injection omitted; no fitted correction.','Two levels and three frames do not establish INL/DNL, ENOB or a calibrated transfer.'])
(P/'evidence'/('sar-sampler-double-ideal-transfer.json' if args.sampler_double else 'sar-clamped-ideal-transfer.json' if args.clamped else 'sar-divider-ideal-transfer.json' if args.divider else 'sar-rzero-ideal-transfer.json' if args.rzero else 'sar-ideal-transfer.json')).write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['variant'],r['hold_ns'],'actual/source-ideal/held-ideal',r['actual_code'],r['ideal_source_code'],r['ideal_held_anchor_code'])
