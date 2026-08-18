#!/usr/bin/env python3
"""Compose extracted 5-bit DAC and phase interpolator across representative PVT."""
from __future__ import annotations
import argparse,concurrent.futures,json,re,subprocess,sys
from pathlib import Path
sys.path.insert(0,"/src/phase_control_dac")
from run_dc import PORTS,bit_sources,instantiate

ENVIRONMENTS=(("typical","res_typical",3.30,27,0.50),("ff","res_ff",2.97,-40,0.45),("ff","res_ss",2.97,125,0.55),
 ("ff","res_typical",3.63,-40,0.55),("ff","res_ff",3.63,125,0.45),("ss","res_ss",2.97,-40,0.55),
 ("ss","res_ff",2.97,125,0.45),("ss","res_typical",3.63,-40,0.45),("ss","res_ss",3.63,125,0.55))
NAMES=("phase_delay","b_delay","diff_high","diff_low","output_cm","supply_current","duty_high","ctrl_a","ctrl_b")
RX=re.compile(r"^("+"|".join(NAMES)+r")\s*=\s*([-+0-9.eE]+)",re.M); PERIOD=800e-12
# The two independent DACs expose 1024 combinations.  Four nested perimeters
# cover high and low effective device overdrive without an exhaustive search.
# This matters because the useful control common mode shifts substantially with
# process and temperature; silicon calibration chooses among these 263 pairs.
CONTROL_LEVELS=(19,23,27,31,29)
CANDIDATE_PAIRS=tuple(pair for level in CONTROL_LEVELS for pair in
 tuple([(level,b) for b in range(level+1)]+[(a,level) for a in range(level-1,-1,-1)]))
TARGET_COUNT=31
def main():
 p=argparse.ArgumentParser(); p.add_argument('--source',required=True,type=Path); p.add_argument('--dac-pex',required=True,type=Path); p.add_argument('--pi-pex',required=True,type=Path)
 p.add_argument('--work',required=True,type=Path); p.add_argument('--output',required=True,type=Path); p.add_argument('--jobs',type=int,default=4)
 p.add_argument('--reuse-complete',action='store_true'); a=p.parse_args(); a.work.mkdir(parents=True,exist_ok=True)
 template=(a.source/'phase_control_integration/composed_tb.spice.in').read_text(); specs=[]
 for env in ENVIRONMENTS:
  mos,res,vdd,temp,cm=env
  for index,(ca,cb) in enumerate(CANDIDATE_PAIRS):
   cid=f"{mos}_{res}_{vdd:.2f}_{temp:+d}_cm{cm:.2f}_k{index:02d}".replace('+','p').replace('-','m').replace('.','p')
   vals={'MOS_CORNER':mos,'RES_CORNER':res,'TEMP_C':str(temp),'VDD_V':f'{vdd:.2f}','VCM_V':f'{vdd*cm:.6f}',
    'DAC_PEX':str(a.dac_pex),'PI_PEX':str(a.pi_pex),'BIT_SOURCES':bit_sources(ca,cb,vdd),'DAC_PORTS':' '.join(PORTS)}
   specs.append((cid,list(env),index,ca,cb,vals))
 def sim(spec):
  cid,env,index,ca,cb,vals=spec; deck=a.work/f'{cid}.spice'; log=a.work/f'{cid}.log'; deck_text=instantiate(template,vals)
  reusable=a.reuse_complete and deck.exists() and log.exists() and deck.read_text()==deck_text
  o={k:float(v) for k,v in RX.findall(log.read_text())} if reusable else {}
  rc=0
  if len(o)!=len(NAMES):
   deck.write_text(deck_text)
   with log.open('w') as out: rc=subprocess.run(['ngspice','-b',str(deck)],stdout=out,stderr=subprocess.STDOUT,timeout=120,check=False).returncode
   o={k:float(v) for k,v in RX.findall(log.read_text())}
  complete=rc==0 and len(o)==len(NAMES); peak=max(o.get('diff_high',0),-o.get('diff_low',0))/2
  electrical=complete and o['diff_high']>=.20 and o['diff_low']<=-.20 and abs(o['diff_high']+o['diff_low'])<=.020 and o['output_cm']-peak>=.25 and o['output_cm']+peak<=env[2]-.10 and .001<=o['supply_current']<=.010 and abs((o['duty_high']%PERIOD)-PERIOD/2)<=12e-12
  return {'id':cid,'environment':env,'candidate_index':index,'dac_codes':[ca,cb],'observed':o,'result':'pass' if electrical else 'fail'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex: cases=list(ex.map(sim,specs))
 groups=[]
 for env in map(list,ENVIRONMENTS):
  all_members=[c for c in cases if c['environment']==env]
  m=sorted((c for c in all_members if c['result']=='pass'),key=lambda c:c['observed']['phase_delay']%PERIOD)
  valid=len(all_members)==len(CANDIDATE_PAIRS) and len(m)>=TARGET_COUNT; metrics={}
  if valid:
   delays=[c['observed']['phase_delay']%PERIOD for c in m]; span=delays[-1]-delays[0]
   targets=[delays[0]+i*span/(TARGET_COUNT-1) for i in range(TARGET_COUNT)]
   selected=[]
   for target in targets:
    available=[i for i,d in enumerate(delays) if not selected or i>selected[-1]]
    selected.append(min(available,key=lambda i:abs(delays[i]-target)))
   chosen=[m[i] for i in selected]; chosen_delays=[delays[i] for i in selected]
   errors=[x-y for x,y in zip(chosen_delays,targets)]; steps=[y-x for x,y in zip(chosen_delays,chosen_delays[1:])]
   metrics={'eligible_candidate_count':len(m),'rejected_candidate_count':len(all_members)-len(m),
    'span_s':span,'minimum_calibrated_phase_step_s':min(steps),'maximum_calibrated_phase_step_s':max(steps),
    'maximum_calibrated_error_s':max(abs(x) for x in errors),'selected_candidate_indices':selected,
    'selected_dac_codes':[c['dac_codes'] for c in chosen],
    'selected_controls_v':[[c['observed']['ctrl_a'],c['observed']['ctrl_b']] for c in chosen]}
   valid=all(x>0 for x in steps) and 160e-12<=span<=240e-12 and max(abs(x) for x in errors)<=4e-12
  groups.append({'environment':env,'observed':metrics,'result':'pass' if valid else 'fail'})
 complete=sum(len(c['observed'])==len(NAMES) for c in cases); passing=sum(g['result']=='pass' for g in groups); result={'schema_version':1,'result':'pass' if complete==len(cases) and passing==len(groups) else 'fail',
  'case_count':len(cases),'complete_case_count':complete,'group_count':len(groups),'passing_group_count':passing,
  'calibration':'per-environment monotone nearest-target selection','candidate_code_pairs':[list(x) for x in CANDIDATE_PAIRS],
  'retained_phase_code_count':TARGET_COUNT,'groups':groups,'cases':cases}
 a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n'); print(f"extracted DAC+PI: {complete}/{len(cases)} complete; {passing}/{len(groups)} environments pass")
 if result['result']!='pass': raise SystemExit(1)
if __name__=='__main__': main()
