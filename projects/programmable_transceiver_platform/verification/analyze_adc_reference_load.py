#!/usr/bin/env python3
"""Measured reference fixture demand, not qualification of a real reference driver."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-sar8-mim-frames'
r=json.loads((P/'evidence/adc-sar8-mim-frames-screen.json').read_text());assert not r['pending_or_incomplete_cases'];rows=[]
for c in r['cases']:
 name=c['name'];file=W/(name+'.dat');assert hashlib.sha256(file.read_bytes()).hexdigest()==c['artifacts_sha256']['.dat']
 d=(W/(name+'.spice')).read_text()
 for line in ('VHR HR 0 2.15','VLR LR 0 1.15','RHR HR VH 10','RLR LR VL 10','CHR VH 0 10p','CLR VL 0 10p'):assert line+'\n' in d
 a=np.loadtxt(file,skiprows=1);t=a[:,0];rails=[]
 for col,nom,label in ((43,2.15,'high'),(44,1.15,'low')):
  current=(nom-a[:,col])/10;active=(t>=60e-9)&(t<=209.7e-9);frames=[]
  for hold in (70,120,170):
   w=(t>=(hold-10)*1e-9)&(t<=(hold+39.7)*1e-9);tw=t[w];v=a[w,col];i=current[w]
   source_charge=float(np.trapezoid(i,tw));reservoir_charge=float(10e-12*(v[-1]-v[0]))
   frames.append(dict(hold_ns=hold,source_net_charge_pc=source_charge*1e12,source_positive_charge_pc=float(np.trapezoid(np.maximum(i,0),tw)*1e12),source_negative_charge_pc=float(np.trapezoid(np.minimum(i,0),tw)*1e12),capacitor_net_charge_pc=reservoir_charge*1e12,inferred_net_charge_to_connected_load_pc=(source_charge-reservoir_charge)*1e12))
  rails.append(dict(rail=label,peak_source_current_ma=float(current[active].max()*1e3),peak_sink_current_ma=float(-current[active].min()*1e3),max_absolute_voltage_error_mv=float(np.max(abs(a[active,col]-nom))*1e3),frames=frames))
 rows.append(dict(name=name,rails=rails,waveform_sha256=c['artifacts_sha256']['.dat']))
out=dict(status='finite_reference_fixture_demand_audited',cases=rows,limitations=['Demand measured with existing 10ohm source impedance and 10pF reservoir; changing driver impedance changes the load waveform.', 'Both sourcing and sinking capability observed; peaks are not final design ratings or a proved worst-case envelope.', 'No actual reference/bias generator, startup, noise or coupled supply qualification.'])
(P/'evidence/adc-reference-load-audit.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps([dict(rail=label,max_source_ma=max(x['peak_source_current_ma'] for c in rows for x in c['rails'] if x['rail']==label),max_sink_ma=max(x['peak_sink_current_ma'] for c in rows for x in c['rails'] if x['rail']==label),max_error_mv=max(x['max_absolute_voltage_error_mv'] for c in rows for x in c['rails'] if x['rail']==label)) for label in ('high','low')],indent=2))
