"""Validate observed SAR trial sequence against observed comparator decisions."""
import numpy as np

def expected_trials(decisions):
    assert len(decisions)==8 and all(d in (0,1) for d in decisions)
    kept=0;trials=[]
    for j,keep in enumerate(decisions):
        bit=7-j;trials.append(kept|(1<<bit))
        if keep:kept|=1<<bit
    return trials,kept

def controls():
    decisions=[0,1,0,1,0,1,0,1]
    trials,code=expected_trials(decisions)
    assert trials==[128,64,96,80,88,84,86,85] and code==85
    assert expected_trials([0]*8)[1]==0 and expected_trials([1]*8)[1]==255

def inspect(header,data):
    controls();t=data[:,0]
    def at(node,time):return float(np.interp(time,t,data[:,header.index('v('+node+')')]))
    def bit(value):
        if value<=.33:return 0
        if value>=2.97:return 1
        raise ValueError('Logic output outside diagnostic rail limits')
    rows=[]
    for hold in (70,120,170):
        decisions=[];trials=[];analog=[]
        try:
            for j in range(8):
                pre=(hold+.4+5*j)*1e-9;decision=(hold+2.4+5*j)*1e-9
                trials.append(sum(bit(at('d'+str(k),pre))<<k for k in range(8)))
                qp,qn=bit(at('qp',decision)),bit(at('qn',decision))
                if qp==qn:raise ValueError('Comparator outputs not complementary')
                decisions.append(qn)
                analog.append(at('hp',(hold+.5+5*j)*1e-9)-at('hn',(hold+.5+5*j)*1e-9))
            final_time=(hold+39)*1e-9
            final=sum(bit(at('d'+str(k),final_time))<<k for k in range(8))
            done=bit(at('done',final_time))
            expected,code=expected_trials(decisions)
            rows.append(dict(hold_ns=hold,logic_valid=True,trials=trials,decisions=decisions,
                expected_trials=expected,decision_code=code,final_code=final,done=done,
                sequence_consistent=trials==expected and code==final and done==1,
                preclock_residues_v=analog))
        except ValueError as error:
            rows.append(dict(hold_ns=hold,logic_valid=False,sequence_consistent=False,reason=str(error)))
    return rows
