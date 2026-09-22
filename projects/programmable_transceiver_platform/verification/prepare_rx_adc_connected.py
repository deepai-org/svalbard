#!/usr/bin/env python3
"""Compose actual retained RF and dual-ADC circuits; preparation, not qualification."""
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
RX=R/'scratch/transceiver-bb-connected-bypass/tone.spice'
ADC=R/'scratch/transceiver-adc-reference-current/frames.spice'
O=R/'scratch/transceiver-rx-adc-connected-prepared';O.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Only completed parent artifacts may supply the retained circuits.
for p in (RX,ADC):
 r=json.loads((p.parent/'result.json').read_text())
 assert r['source_sha256_before']==r['source_sha256_after']
 case=next(c for c in r['cases'] if c['name']==p.stem) if 'cases' in r else r
 assert case['returncode']==0 and not case['timed_out']
 for ext,expected in case['artifacts_sha256'].items():
  assert sha(p.parent/(p.stem+ext))==expected
rx=RX.read_text().split('.control')[0]
adc=ADC.read_text().split('.control')[0]
global_lines=[]
def separate(text):
 body=[];defs=[];depth=0
 for line in text.splitlines():
  low=line.lower().strip()
  if low.startswith('.subckt'):depth+=1
  if depth:
   defs.append(line)
   if low.startswith('.ends'):depth-=1
  elif low.startswith(('.include ','.lib ','.temp ')):
   if line not in global_lines:global_lines.append(line)
  else:body.append(line)
 assert depth==0
 return body,defs
rxbody,rxdefs=separate(rx);abody,adefs=separate(adc)
assert not rxdefs
initial=[];kept=[]
for line in rxbody:
 if line.lower().startswith('.ic '):
  initial.append(re.sub(r'v\(', 'v(XRX.',line,flags=re.I))
 else:kept.append(line)
rxbody=kept
removed=[];new=[];shifted=[]
remove={'VIP','VIN','RIP','RIN','VQ_IP','VQ_IN','RQ_IP','RQ_IN'}
for line in abody:
 parts=line.split()
 if parts and parts[0] in remove:removed.append(line);continue
 if 'PWL(' in line:
  old=line
  def shift(m):
   value=float(m.group(1));return (f'{value+400:.12g}' if value else '0')+'n'
  line=re.sub(r'(?<![\w.])([0-9]+(?:\.[0-9]+)?)n\b',shift,line)
  shifted.append(dict(before=old,after=line))
 new.append(line)
assert len(removed)==8 and len(shifted)==7
# No input sources or substitute impedances remain between filters and drivers.
assert all(not l.startswith(tuple(x+' ' for x in remove)) for l in new)
text='* Actual RF receiver connected directly to both actual ADC sample drivers\n'
text+='\n'.join(global_lines+adefs)+'\n'
text+='.subckt pt_rx_loaded FIP FIN FQP FQN\n'+'\n'.join(rxbody)+'\n.ends pt_rx_loaded\n'
text+='.subckt pt_adc_pair_loaded GP GN Q_GP Q_GN\n'+'\n'.join(new)+'\n.ends pt_adc_pair_loaded\n'
text+='XRX FIP FIN FQP FQN pt_rx_loaded\nXADC FIP FIN FQP FQN pt_adc_pair_loaded\n'+'\n'.join(initial)+'\n'
text+='''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 2p 610n 0 2p uic
wrdata /work/connected.dat v(FIP) v(FIN) v(FQP) v(FQN) v(XADC.IP) v(XADC.IN) v(XADC.Q_IP) v(XADC.Q_IN) v(XADC.HP) v(XADC.HN) v(XADC.Q_HP) v(XADC.Q_HN) v(XADC.VH) v(XADC.VL) i(v.XRX.VBB) i(v.XADC.VBUF) i(v.XADC.VREFSUP)
.endc
.end
'''
(O/'connected.spice').write_text(text)
m=dict(parent_decks={str(p.relative_to(R)):sha(p) for p in (RX,ADC)},deck_sha256=sha(O/'connected.spice'),removed_input_fixture_lines=removed,shifted_clock_sources=shifted,scope='Prepared connected circuit, not elaborated or simulated yet.',initialization='RF seeded UIC now applies to ADC too; first acquisition ends470ns. ADC bias/startup must be verified; not cold-start qualification.',limitations=['RF oscillator control remains ideal; autonomous PLL not integrated in this fixture.','Supplies/bias targets and ADC clocks remain ideal.','RF input is the retained single-ended1mV tone; differential pad contract not qualified.','No claim of noise, ENOB or timing closure.'],next_checks=['Inspect hierarchy and model elaboration with a short preflight.','Verify ADC UIC bias/startup before scoring conversion.','Save physical ADC decisions, controls and driver bias vectors before full run.','Prepare matched unloaded receiver with identical history and initialization.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
(P/'evidence/rx-adc-connected-preparation.json').write_text(json.dumps(m,indent=2)+'\n')
print('Prepared connected RF/filter/dual-ADC schematic; simulation gate remains pending.')
