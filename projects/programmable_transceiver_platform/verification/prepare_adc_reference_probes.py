#!/usr/bin/env python3
"""Prepare terminal-current observation replay of latest actual-reference dual ADC."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-adc-shared-iq-damping2k';O=R/'scratch/transceiver-adc-reference-current-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads((P/'evidence/adc-shared-iq-damping2k.json').read_text());assert e['completed']
r=json.loads((B/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']
for ext,h in r['artifacts_sha256'].items():assert sha(B/('frames'+ext))==h
base=(B/'frames.spice').read_text();changes={
'XREF HR LR VH VL RBN RBP VREFSUP 0 pt_adc_reference_pair_tuned':'XREF HR LR VHDRV VLDRV RBN RBP VREFSUP 0 pt_adc_reference_pair_tuned',
'XHR VH 0 pt_ref_reservoir_2048':'XHR VHRES 0 pt_ref_reservoir_2048',
'XLR VL 0 pt_ref_reservoir_2048':'XLR VLRES 0 pt_ref_reservoir_2048'}
d=base
for old,new in changes.items():assert d.count(old)==1;d=d.replace(old,new)
sensors='VREFH_DEL VHDRV VH 0\nVREFL_DEL VLDRV VL 0\nVREFH_RES VH VHRES 0\nVREFL_RES VL VLRES 0\n'
d=d.replace('.control',sensors+'.control')
old=next(x for x in d.splitlines() if x.startswith('wrdata '));new=old+' i(VREFH_DEL) i(VREFL_DEL) i(VREFH_RES) i(VREFL_RES) v(VHDRV) v(VLDRV) v(VHRES) v(VLRES)';d=d.replace(old,new)
rev=d.replace(new,old).replace(sensors,'')
for a,b in changes.items():rev=rev.replace(b,a)
assert rev==base
O.mkdir(exist_ok=True);(O/'frames.spice').write_text(d)
m=dict(baseline_deck_sha256=sha(B/'frames.spice'),prepared_deck_sha256=sha(O/'frames.spice'),exact_reversal_verified=True,source_sha256_before=r['source_sha256_before'],sensor_directions={'VREFH_DEL':'high driver to rail','VREFL_DEL':'low driver to rail','VREFH_RES':'high rail into reservoir','VREFL_RES':'low rail into reservoir'},derived_current='ADC rail demand = delivered driver current minus reservoir current; signed, including both channels.',validation_required=['All original waveform columns must reproduce within measured/reported tolerance before interpreting probe currents.','Check nominal zero-voltage sensor constraints and waveform completion.','Different solver behavior after adding sensors is not a physical design change.'],scope='Observation-only zero-volt series sensors; no capacitor/device/timing/voltage-value change.')
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');(P/'evidence/adc-reference-current-preparation.json').write_text(json.dumps(m,indent=2)+'\n');print('four terminal sensors; exact reversal verified')
