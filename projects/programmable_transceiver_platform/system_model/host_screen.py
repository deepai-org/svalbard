"""Contract-derived per-direction transport screen; not FIFO/CDC verification."""
import hashlib
import json
import math
from pathlib import Path
P=Path(__file__).resolve().parents[1]

def budget(transport,profile,rates):
    p=transport['profiles'][profile]
    slots=transport['frame_words']-transport['control_words']
    word_rate=p['clock_hz']*p['edges']*(1-transport['host_slow_ppm']*1e-6)
    frame_rate=word_rate/transport['frame_words']
    stressed={k:v*(1+transport['source_fast_ppm']*1e-6) for k,v in rates.items()}
    required={k:math.ceil(v/(frame_rate*transport['word_bits'])) for k,v in stressed.items()}
    capacity=slots*frame_rate*transport['word_bits']; demand=sum(stressed.values())
    return dict(profile=profile,rates_bps=rates,payload_capacity_bps=capacity,
        demand_bps=demand,margin_bps=capacity-demand,
        required_slots=required,available_slots=slots,
        aggregate_rate_fits=demand<=capacity,static_slot_counts_fit=sum(required.values())<=slots)

def main():
    path=P/'spec/contract.json';contract=json.loads(path.read_text());t=contract['transport']
    cases=[]
    for mode in contract['modes']:
        for direction in ['d2h','h2d']:
            rates={s['id']:s['rate_bps'] for s in mode['sources'] if direction in s['directions']}
            cases.append(dict(mode=mode['id'],direction=direction,**budget(t,mode['profile'],rates)))
    # Explicit reconciliation with fast_screen's hypothetical 40MS/s,8-bit I/Q.
    for wire in [0,1.25e9,2.5e9]:
        for profile in t['profiles']:
            cases.append(dict(mode='fast_rf_40MSps_8bit_per_IQ',direction='each independently',
                **budget(t,profile,dict(iq=40e6*2*8,wire=wire))))
    assert budget(t,'sdr25',{'zero':0})['required_slots']=={'zero':0}
    assert not budget(t,'sdr25',{'overload':1e10})['aggregate_rate_fits']
    report=dict(status='architecture_budget_not_transport_qualification',
        contract_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases=cases,
        limitations=['Static slot ceilings and aggregate capacity only; not schedule/FIFO/CDC simulation.',
        'Rates refer to separate physical directions; do not sum both into one bus.',
        'Host electrical timing and FPGA capability are unqualified.',
        'Fast RF waveform is not yet packed into transport words.',
        'Declared source/host ppm are planning assumptions, not guaranteed limits.'])
    (P/'evidence/fast-host-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    for c in cases:
        print(c['mode'],c['profile'],c['direction'],c['static_slot_counts_fit'],round(c['margin_bps']/1e6,2),'Mb/s margin')
if __name__=='__main__':main()
