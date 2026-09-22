#!/usr/bin/env python3
"""Audit completed PDK-MIM streams, preserving failed decisions and partial coverage."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--require-complete',action='store_true');parser.add_argument('--fast-comp',action='store_true');parser.add_argument('--reference-driver',action='store_true');parser.add_argument('--reservoir',action='store_true');parser.add_argument('--reference-compensated',action='store_true');parser.add_argument('--reference-output2',action='store_true');args=parser.parse_args();args.reference_compensated=args.reference_compensated or args.reference_output2;args.reservoir=args.reservoir or args.reference_compensated;args.reference_driver=args.reference_driver or args.reservoir;args.fast_comp=args.fast_comp or args.reference_driver
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
tag='sar8-reference-output2' if args.reference_output2 else 'sar8-reference-compensated' if args.reference_compensated else 'sar8-reference-reservoir' if args.reservoir else 'sar8-reference-driver' if args.reference_driver else ('sar8-mim-fast-comp' if args.fast_comp else 'sar8-mim-frames')
W=R/('scratch/transceiver-adc-'+tag);B=R/'scratch/transceiver-adc-sar8-strong-mask-frames'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if args.reference_compensated:
 manifest=json.loads((W/'manifest.json').read_text())
 for path,digest in manifest['source_sha256_before'].items():
  if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==digest
 terminal=W/'result.json'
 if terminal.exists():
  result=json.loads(terminal.read_text());assert result['source_sha256_before']==result['source_sha256_after']==manifest['source_sha256_before']
 record=W/('result.json' if terminal.exists() else 'progress.json')
 runrecord=json.loads(record.read_text()) if record.exists() else {'cases':[]}
base=json.loads((P/'evidence/adc-sar8-strong-mask-frames-screen.json').read_text())
for path,digest in base['source_sha256'].items():
 local=P/'analog'/path.removeprefix('/screen/') if path.startswith('/screen/') else R/'ip/blocks/analog/wifi_80211b'/path.removeprefix('/wifi/')
 assert sha(local)==digest
if args.reference_driver:
 for auditname in ('reference-buffer-dc-screen.json','reference-buffer-complement-dc-screen.json'):
  for path,digest in json.loads((P/'evidence'/auditname).read_text())['source_sha256'].items():
   assert sha(P/'analog'/path.removeprefix('/screen/'))==digest
 pair=(P/'analog/reference/adc_reference_pair.spice').read_text()
 assert 'XHIGH HIGH_TARGET VH BN BP VDD VSS pt_reference_buffer_complement S=4' in pair
 assert 'XLOW LOW_TARGET VL BN BP VDD VSS pt_reference_buffer_scaled S=4' in pair
# Check explicit unit counts, complementary wiring and switch scaling.
s=(P/'analog/adc/cdac8_mim.spice').read_text()
for i in range(8):
 block=s.split(f'.subckt pt_cdac_mim_bit{i} ')[1].split('.ends')[0]
 caps=[x for x in block.splitlines() if x.startswith('XC')]
 assert len(caps)==2**i
 assert all(x.endswith('TOP BOT cap_mim_1f5_m4m5_noshield c_length=5u c_width=5u') for x in caps)
 assert f'XH VH BOT B BB VDD VSS pt_cdac_scaled_switch S={2**i}' in block
 assert f'XL VL BOT BB B VDD VSS pt_cdac_scaled_switch S={2**i}' in block
 assert f'XP{i} HP VH VL B{i} B{i}B VDD VSS pt_cdac_mim_bit{i}' in s
 assert f'XN{i} HN VH VL B{i}B B{i} VDD VSS pt_cdac_mim_bit{i}' in s
assert 'XDP HP VL cap_mim_1f5_m4m5_noshield c_length=5u c_width=5u' in s
assert 'XDN HN VL cap_mim_1f5_m4m5_noshield c_length=5u c_width=5u' in s
rows=[];missing=[]
for corner in (('typical',) if args.reference_driver else ('typical','ss','ff')):
 for sign in (-1,1):
  name=f'{corner}_first{sign}';file=W/(name+'.dat');log=W/(name+'.log')
  if not file.exists() or not log.exists() or 'Note: Simulation executed from .control section' not in log.read_text():
   missing.append(name);continue
  d=(W/(name+'.spice')).read_text();original=(B/f'first{sign}.spice').read_text()
  reference=next(c for c in base['cases'] if c['name']==f'first{sign}')
  assert sha(B/f'first{sign}.spice')==reference['artifacts_sha256']['.spice']
  if args.reference_compensated:
   record=next(c for c in runrecord['cases'] if c['name']==name)
   assert record['returncode']==0 and not record['timed_out']
   for ext,digest in record['artifacts_sha256'].items():assert sha(W/(name+ext))==digest
   assert sha(W/(name+'.spice'))==record['deck_sha256_before']
   if args.reference_output2:
    directbase=R/'scratch/transceiver-adc-sar8-reference-compensated'/(name+'.spice')
    assert sha(directbase)==record['baseline_deck_sha256']
    d=d.replace('/screen/reference/adc_reference_pair_output2.spice','/screen/reference/adc_reference_pair_tuned.spice').replace(' pt_adc_reference_pair_output2\n',' pt_adc_reference_pair_tuned\n')
    assert d==directbase.read_text()
   refbase=R/'scratch/transceiver-adc-sar8-reference-reservoir'/(name+'.spice')
   if not args.reference_output2:assert sha(refbase)==record['baseline_deck_sha256']
   d=d.replace('/screen/reference/adc_reference_pair_tuned.spice','/screen/reference/adc_reference_pair.spice').replace(' pt_adc_reference_pair_tuned\n',' pt_adc_reference_pair\n')
   assert d==refbase.read_text()
  if args.reservoir:
   replacement='.include /screen/reference/reservoir_mim.spice\nXHR VH 0 pt_ref_reservoir_2048\nXLR VL 0 pt_ref_reservoir_2048\n'
   assert replacement in d
   d=d.replace(replacement,'CHR VH 0 10p\nCLR VL 0 10p\n')
   assert d==(R/'scratch/transceiver-adc-sar8-reference-driver'/(name+'.spice')).read_text()
  if args.reference_driver:
   extra='.include /screen/reference/adc_reference_pair.spice\nVREFSUP VREFSUP 0 3.3\nIRBN VREFSUP RBN 20u\nIRBP RBP 0 20u\nXRBN RBN RBN 0 0 nfet_03v3 w=8u l=.5u\nXRBP RBP RBP VREFSUP VREFSUP pfet_03v3 w=8u l=.5u\nXREF HR LR VH VL RBN RBP VREFSUP 0 pt_adc_reference_pair\n'
   assert extra in d
   d=d.replace(extra,'RHR HR VH 10\nRLR LR VL 10\n').replace(' i(VREFSUP) v(XREF.XHIGH.X) v(XREF.XLOW.X)','')
   assert d==(R/'scratch/transceiver-adc-sar8-mim-fast-comp'/(name+'.spice')).read_text()
  if args.fast_comp:
   assert d.count(' CC=.5p\n')==2
   d=d.replace(' CC=.5p\n','\n')
   assert d==(R/'scratch/transceiver-adc-sar8-mim-frames'/(name+'.spice')).read_text()
  restored=d.replace('pt_cdac8_mim','pt_cdac8_scaled').replace(f'/work/{name}.dat',f'/work/first{sign}.dat')
  restored=restored.replace(f'.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_{corner}\n.include /screen/adc/cdac8_mim.spice\n','')
  restored=restored.replace(' v(B7) v(B7B) v(xd.xp7.bot) v(xd.xn7.bot) v(VH) v(VL)','')
  assert restored==original,'Unexpected circuit or fixture change'
  a=np.loadtxt(file,skiprows=1);assert a.shape[1]==(48 if args.reference_driver else 45) and np.isfinite(a).all() and a[-1,0]>=209.9e-9
  def win(lo,hi):
   w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];assert len(w)>1;return w
  def logic(w,col):
   if np.all(w[:,col]>2.97):return 1
   if np.all(w[:,col]<.33):return 0
   return None
  def code(w,start=8):
   bits=[logic(w,start+i) for i in range(8)]
   return None if None in bits else sum(b*2**i for i,b in enumerate(bits))
  frames=[]
  for n,hold in enumerate((70,120,170)):
   vin=sign*.4*(-1)**n;steps=[];trial=128
   for bit in range(7,-1,-1):
    edge=hold+2.5+5*(7-bit);before=win(edge-.5,edge-.2)
    after=win(edge+1.8,edge+2.2) if bit==0 else win(edge+2.5,edge+2.8)
    pre=win(edge-2.3,edge-2.15);res=float(np.mean(pre[:,1]-pre[:,2]));keep=logic(before,27)
    expected=None if trial is None or keep is None else ((trial if keep else trial&~(1<<bit)) | (1<<(bit-1) if bit else 0))
    steps.append(dict(bit=bit,residue_v=res,keep=keep,decision_agrees=keep is not None and keep==int(res<0),trial_valid=trial is not None and code(before)==trial and code(before,31)==trial,capture_valid=expected is not None and code(after)==expected,token_valid=code(after,16)==(1<<(bit-1) if bit else 0),done_valid=logic(after,7)==int(bit==0)))
    trial=expected
   final=win(hold+39.3,hold+39.7);sample=win(hold+.2,hold+.35)
   pretrack=None
   if n:
    w=win(hold-10.2,hold-10.05)
    pretrack=dict(msb_gate_high_min_v=float(w[:,39].min()),msb_gate_low_max_v=float(w[:,40].max()),positive_plate_error_max_v=float(np.max(abs(w[:,41]-w[:,43]))),negative_plate_error_max_v=float(np.max(abs(w[:,42]-w[:,44]))))
   active=win(hold-10,hold+39.7)
   frames.append(dict(hold_ns=hold,input_v=vin,final_code=code(final),final_capture_valid=trial is not None and code(final)==trial and logic(final,7)==1,held_differential_v=float(np.mean(sample[:,1]-sample[:,2])),held_error_v=float(np.mean(sample[:,1]-sample[:,2])-vin),reference_high_range_v=[float(active[:,43].min()),float(active[:,43].max())],reference_low_range_v=[float(active[:,44].min()),float(active[:,44].max())],pretrack_msb=pretrack,steps=steps))
  if args.reference_driver:
   for frame in frames:
    w=win(frame['hold_ns']-10,frame['hold_ns']+39.7)
    frame['reference_supply_peak_ma']=float(np.max(-w[:,45])*1e3)
    frame['reference_supply_average_ma']=float(-np.trapezoid(w[:,45],w[:,0])/(w[-1,0]-w[0,0])*1e3)
  rows.append(dict(name=name,frames=frames,artifacts_sha256={ext:sha(W/(name+ext)) for ext in ('.spice','.dat','.log')}))
r=dict(status='partial_PDK_MIM_waveform_audit' if missing else 'completed_PDK_MIM_waveform_audit',cases=rows,pending_or_incomplete_cases=missing,explicit_unit_count=512,cdac_source_sha256=sha(P/'analog/adc/cdac8_mim.spice'),qualified_adc=False,limitations=['Conditional MIM process option; PDK corners are not bounds on fab unknowns.', 'External clocks, ideal bias/reference generators; finite reference impedance included.', 'Six selected streams do not prove transfer accuracy, noise, mismatch, 40MS/s or RF integration.', 'Pretrack bottom-plate error is reported, not assigned an unsubstantiated passing threshold.'])
if args.reservoir:
 reservoir_audit=json.loads((P/'evidence/reference-reservoir-model.json').read_text())
 assert sha(P/'analog/reference/reservoir_mim.spice')==reservoir_audit['source_sha256']
 r['reservoir_units_per_rail']=2048
 r['reservoir_source_sha256']=reservoir_audit['source_sha256']
r['actual_reference_output_drivers']=bool(args.reference_driver)
if args.reference_driver:
 r['limitations']=['Actual reference drivers but ideal targets, bias currents and separate supply.', 'Nominal MIM only; compensation/reservoir capacitors ideal; no noise/mismatch/startup/stability qualification.']
 if args.reservoir:r['limitations'].append('Reservoirs use 2048 explicit PDK MIM units per rail; their layout/parasitics and process option are unqualified.')
 r['reference_pair_source_sha256']=sha(P/('analog/reference/adc_reference_pair_output2.spice' if args.reference_output2 else 'analog/reference/adc_reference_pair_tuned.spice' if args.reference_compensated else 'analog/reference/adc_reference_pair.spice'))
if args.reference_compensated:
 r['reference_output_stage_multiplier']=2 if args.reference_output2 else 1
 r['reference_compensation_per_amplifier']={'capacitance_pf':8,'series_resistance_ohm':500}
 r['reference_run_sources_consistent_after_execution']=bool(terminal.exists())
 r['reference_source_manifest']=manifest
r['compensation_pf']=.5 if args.fast_comp else 1
r['all_completed_logic_and_decision_checks_pass']=bool(rows) and all(f['final_capture_valid'] and all(step[key] for step in f['steps'] for key in ('decision_agrees','trial_valid','capture_valid','token_valid','done_valid')) for c in rows for f in c['frames'])
(P/('evidence/adc-'+tag+'-screen.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(completed=[dict(name=c['name'],codes=[f['final_code'] for f in c['frames']],held_errors_v=[f['held_error_v'] for f in c['frames']]) for c in rows],pending=missing),indent=2))

if args.require_complete:
 assert not missing, 'Corner/sequence coverage incomplete; partial evidence retained'
 assert r['all_completed_logic_and_decision_checks_pass'], 'Decision/logic failures retained in evidence'
