#!/usr/bin/env python3
"""Enforce phase-control DAC electrical, physical, and settling evidence."""
import argparse,hashlib,json,re
from pathlib import Path
def main():
 p=argparse.ArgumentParser()
 for n in ('schematic','extracted','settling','drc','lvs','pex','gds','render','output'): p.add_argument(f'--{n}',required=True,type=Path)
 a=p.parse_args(); s=json.loads(a.schematic.read_text()); e=json.loads(a.extracted.read_text()); t=json.loads(a.settling.read_text()); pt=a.pex.read_text(); nr=len(re.findall(r'^R\d+\s',pt,re.M)); nc=len(re.findall(r'^C\d+\s',pt,re.M))
 checks={'schematic.dc_transfer':s.get('result')=='pass' and s.get('case_count')==288,'extracted.dc_transfer':e.get('result')=='pass' and e.get('case_count')==288,
  'extracted.settling':t.get('result')=='pass' and t.get('passing_case_count')==9,'magic.drc_zero':'[INFO] COUNT: 0' in a.drc.read_text(),
  'netgen.lvs_unique':'Final result: Circuits match uniquely.' in a.lvs.read_text(),'pex.full_rc':'.subckt phase_control_dac_pex' in pt and 'extresist threshold=0 mOhm' in pt and nr>=200 and nc>=100,
  'layout.rendered':a.render.stat().st_size>=10000}
 result={'schema_version':1,'result':'pass' if all(checks.values()) else 'fail','qualification':'experimental pre-silicon GF180 public-model evidence only','checks':checks,
  'layout_sha256':hashlib.sha256(a.gds.read_bytes()).hexdigest(),'pex':{'resistor_count':nr,'capacitor_count':nc,'sha256':hashlib.sha256(a.pex.read_bytes()).hexdigest()},
  'observed':{'minimum_extracted_step_v':min(min(g['minimum_step_a_v'],g['minimum_step_b_v']) for g in e['groups']),
   'minimum_extracted_high_v':min(g['endpoint_high_v'] for g in e['groups']),'maximum_extracted_reference_power_w':max(g['maximum_abs_reference_power_w'] for g in e['groups']),
   'worst_extracted_settling_ns':max(c['settling_time_s'] for c in t['cases'])*1e9}}
 a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 if result['result']!='pass': raise SystemExit('phase-control DAC checks failed: '+', '.join(k for k,v in checks.items() if not v))
 print('phase_control_dac schematic/layout/PEX checks: PASS')
if __name__=='__main__': main()
