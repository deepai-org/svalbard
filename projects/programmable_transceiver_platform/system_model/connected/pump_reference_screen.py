"""Pulse-loop charge/phase continuity, holdover and reference reacquisition."""
import copy,json
from chip_model import P
from compliant_edge_pll import CompliantEdgePLL

def run(rate,loss):
    p=CompliantEdgePLL(rate_hz=rate,reference_hz=10e6)
    assert p.advance(loss)
    phase=p.phase;capacitors=(p.filter.v,p.filter.w);charge=p.filter.charge
    p.set_reference(False,loss)
    assert p.phase==phase and (p.filter.v,p.filter.w)==capacitors
    assert p.current==0 and not p.locked and p.good==0
    a=copy.copy(p);end=loss+5e-6
    assert p.advance(end)
    for i in range(1,138):assert a.advance(loss+5e-6*i/137)
    assert p.phase>phase and p.filter.charge==charge and p.current==0
    assert abs(a.phase-p.phase)<1e-7 and abs(a.filter.v-p.filter.v)<1e-12
    target=p.phase+3.5;crossing=p.edge_time(target);future=copy.copy(p)
    assert future.advance(crossing) and abs(future.phase-target)<2e-8
    before=(p.phase,p.filter.v,p.filter.w,p.feedback_target)
    p.set_reference(True,end)
    assert before==(p.phase,p.filter.v,p.filter.w,p.feedback_target)
    assert p.next_reference>end and not p.locked
    assert p.advance(end+30e-6) and p.locked
    return dict(rate_hz=rate,loss_s=loss,recovery_start_s=end,phase_subdivision_error=abs(a.phase-before[0]),
        held_pump_charge_c=charge,final_frequency_hz=p.frequency_hz,locked=p.locked)

def main():
    rows=[run(r,t) for r in (1.25e9,2.5e9) for t in (150e-9,20.035e-6)]
    (P/'evidence/connected-pump-reference.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Reference loss instantly gates the pump; physical loss-detection delay is not modeled.',
        'Ideal capacitor retention excludes leakage and noise; passive filter redistribution is preserved.',
        'Reference returns on the original grid; arbitrary returned reference phase remains untested.']),indent=2)+'\n')
    print('Passed pulse-loop holdover, capacitor/phase continuity and reacquisition')
if __name__=='__main__':main()
