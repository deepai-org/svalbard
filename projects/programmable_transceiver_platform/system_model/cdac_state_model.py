"""Charge-conserving ideal-capacitor/finite-switch CDAC transition scaffold."""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.linalg import expm
P=Path(__file__).resolve().parents[1]

def matrix(unit,load):
    weights=2.**np.arange(8);caps=unit*weights
    C=np.zeros((9,9));C[0,0]=256*unit+load
    C[0,1:]=-caps;C[1:,0]=-caps;C[1:,1:]=np.diag(caps)
    assert np.all(np.linalg.eigvalsh(C)>0)
    return C

def rails(code,high=2.15,low=1.15):
    return np.where((code & (1<<np.arange(8)))!=0,high,low)

def advance(state,code,duration,C,unit_resistance):
    # Bottom-node voltages and top voltage remain continuous when code changes.
    conductance=(2.**np.arange(8))/unit_resistance
    # Eliminate the floating top node using its conserved charge, avoiding
    # numerical drift of the zero eigenvalue during long settling intervals.
    charge=(C@state)[0]
    reduced=C[1:,1:]-np.outer(C[1:,0],C[0,1:])/C[0,0]
    A=-np.linalg.solve(reduced,np.diag(conductance))
    target=rails(code)
    bottoms=target+expm(A*duration)@(state[1:]-target)
    top=(charge-C[0,1:]@bottoms)/C[0,0]
    return np.r_[top,bottoms]

def main():
    source=P/'evidence/adc-top-load.json';d=json.loads(source.read_text())
    unit=d['unit_capacitance_ff']*1e-15;load=d['capacitance_per_side_ff'][0]*1e-15
    C=matrix(unit,load);resistance=1300. # Hypothetical per-unit on resistance.
    rows=[]
    for initial,sequence in [(127,[128,127]),(128,[127,128]),(0,[255,0]),(85,[170,85])]:
        state=np.r_[1.65,rails(initial)];original=state.copy();charge=(C@state)[0]
        for code in sequence:
            # Same state at t=0: switching changes derivatives, not capacitor charge.
            assert np.allclose(advance(state,code,0,C,resistance),state,atol=1e-14)
            state=advance(state,code,5e-9,C,resistance)
            expected=original[0]+unit*(code-initial)/(256*unit+load)
            error=abs((C@state)[0]-charge)
            assert error<1e-23 and abs(state[0]-expected)<1e-9
            rows.append(dict(initial_code=initial,selected_code=code,top_v=float(state[0]),expected_settled_v=float(expected),top_charge_error_c=float(error)))
        assert np.max(abs(state-original))<1e-9
    # Equivalent elapsed-time partitions must agree for an unchanged code.
    state=np.r_[1.65,rails(127)]
    direct=advance(state,128,100e-12,C,resistance)
    split=advance(advance(state,128,40e-12,C,resistance),128,60e-12,C,resistance)
    assert np.allclose(direct,split,rtol=1e-12,atol=1e-12)
    report=dict(status='charge_state_controls_only',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases=rows,limitations=['Ideal linear array capacitors plus constant top load; no transistor switching calibration.', '1300ohm unit resistance is a scenario assumption, not a characterized selected-rail law.', 'Ideal abrupt switch selection excludes overlap, dead time, charge injection and clock feedthrough.', 'Fixed ideal rails and fixed dummy bottom; moving references need explicit additional state/input terms.', 'A single-side scaffold; not complete differential SAR or validated broadband clock model.'])
    (P/'evidence/fast-cdac-state.json').write_text(json.dumps(report,indent=2)+'\n')
    print('8 transition checks plus continuity, return and time-partition controls passed')
if __name__=='__main__':main()
