"""Causal charge-domain SAR skeleton; settling, acquisition and comparator ideal."""
import math


def convert(anchor_v,span_v=1.0,bits=8,extra_cap_ratio=0.0,rails=None):
    """Anchor is differential held voltage at initial midscale trial.

    Higher anchor voltage maps to a lower offset-binary code, matching the
    physical comparator convention. Not the signed rounded transport codec.
    rails(bit, trial, previous_trial) may supply causal high/low rail values.
    Callback state is owned by the caller; recorded future rails are not valid.
    """
    assert bits>=2 and span_v>0 and extra_cap_ratio>=0
    total=1<<bits;mid=total//2;beta=1/(1+extra_cap_ratio)
    # Weighted differential bottom potential, including common dummy cancellation.
    def bottom(code,span):return (2*code-(total-1))*span/total
    initial=bottom(mid,span_v);held=anchor_v;previous_bottom=initial
    previous_trial=mid;code=0;steps=[]
    for bit in range(bits-1,-1,-1):
        trial=code+(1<<bit)
        high,low=(span_v,0.) if rails is None else rails(bit,trial,previous_trial)
        assert math.isfinite(high) and math.isfinite(low) and high>low
        current_bottom=bottom(trial,high-low)
        held+=beta*(current_bottom-previous_bottom)
        keep=held<=0
        if keep:code=trial
        steps.append(dict(bit=bit,trial=trial,span_v=high-low,residue_v=held,keep=keep))
        previous_trial=trial;previous_bottom=current_bottom
    return code,steps


def controls():
    # Mid-bin points avoid floating ambiguity at comparator's exact zero.
    for extra in (0.,.005142900034246223,.02):
        beta=1/(1+extra)
        for code in range(256):
            anchor=beta*(128-code-.5)/128
            actual,steps=convert(anchor,extra_cap_ratio=extra)
            assert actual==code
            for s in steps:
                assert abs(s['residue_v']-(anchor+beta*(s['trial']-128)/128))<1e-14
    assert convert(2)[0]==0 and convert(-2)[0]==255
    calls=[]
    def rails(bit,trial,previous):
        calls.append((bit,trial,previous))
        return (1.01 if trial>previous else .99),0
    code,steps=convert(.1,rails=rails)
    assert len(calls)==8 and calls[0][2]==128
    for i in range(1,8):assert calls[i][2]==steps[i-1]['trial']
    assert code==sum(1<<s['bit'] for s in steps if s['keep'])
    return dict(ideal_transfer_cases=768,causal_rail_callback_decisions=8)


if __name__=='__main__':
    import hashlib,json
    from pathlib import Path
    p=Path(__file__).resolve().parents[2]
    report=dict(controls=controls(),status='causal_charge_skeleton_controls_passed',
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['No physical reference dynamics or within-bit bottom-plate settling model.',
          'Anchor supplied: sample acquisition and initial loading excluded.',
          'Ideal comparator, equal linear capacitors, constant top-node loading.',
          'Not yet connected to multicarrier ADC or matched against independent physical decisions.'])
    (p/'evidence/sar-causal-charge-controls.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
