#!/usr/bin/env python3
"""Check measured model behavior; explicit limits prevent assuming physical accuracy."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';W=ROOT/'scratch/transceiver-adc-mim-model'
r=json.loads((W/'result.json').read_text());assert len(r['cases'])==12
assert {(c['corner'],c['par'],c['bias_v']) for c in r['cases']}=={(corner,par,bias) for corner in ('typical','ss','ff') for par in (1,2) for bias in (0,1)}
# Coefficients read from the pinned installed model, including fringe and temperature.
base=(1.47e-3*(5e-6)**2+3.79e-10*20e-6)*(1+4.0604e-5*2-6.90e-8*4)
for c in r['cases']:
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(c['name']+suffix)).read_bytes()).hexdigest()==digest
 a=np.loadtxt(W/(c['name']+'.dat'),skiprows=1);assert len(a)==3 and np.isfinite(a).all() and a[0]==1e6
 measured=-a[2]/(2*np.pi*a[0]);assert np.isclose(measured,c['capacitance_f'],rtol=1e-12,atol=1e-25)
 expected=base*dict(typical=1,ss=1.155,ff=.845)[c['corner']]
 assert np.isclose(measured,expected,rtol=1e-10,atol=1e-24)
r['nominal_unit_capacitance_ff']=base*1e15
r['assumed_20ff_unit_verified']=False
r['installed_pcell_minimum_um']=[5,5]
r['par_2_changes_measured_capacitance']=False
r['dc_bias_0_to_1v_changes_measured_capacitance']=False
r['nominal_256_unit_leg_capacitance_pf']=base*256*1e12
r['interpretation']='Selected installed MIM primitive at its PCell minimum exceeds the ideal 20fF unit. Tested par=2 has no scaling effect; use explicitly verified replication. Bias sweep gives identical small-signal capacitance, consistent with the voltage-dependent expression being commented out in the inspected source; this does not prove real voltage independence.'
r['limitations'].append('PCell minimum is an implementation-interface constraint, not proof that all possible 20fF capacitor structures are impossible. No layout or fabrication-rule qualification performed.')
(P/'evidence/adc-mim-model-audit.json').write_text(json.dumps(r,indent=2)+'\n')
print('Nominal unit fF:',r['nominal_unit_capacitance_ff'],'; 256-unit leg pF:',r['nominal_256_unit_leg_capacitance_pf'])
