"""Keep the lock criteria fixed while testing lower-bandwidth fractional loops."""
import json
from chip_model import P
from fractional_grid_screen import measure

def main():
    targets=(2300000000,2313000000,2329000000,2353000000,2369000000,2393000000,2409000000,2412000000,2437000000,2500000000)
    rows=[]
    for bandwidth in (325e3,300e3):
        for target in targets:rows.append(measure(target,bandwidth))
        print(bandwidth,sum(r['sustained_qualification'] for r in rows if r['bandwidth_hz']==bandwidth),'/',len(targets),flush=True)
    (P/'evidence/connected-fractional-grid-bandwidth.json').write_text(json.dumps(dict(status='characterized',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Six previously failing ratios plus four controls; not a new full-grid qualification.',
        'Lower bandwidth changes filter requirements and noise transfer; acquisition alone does not qualify RF waveform quality.',
        'Lock thresholds, startup phase, free frequency and 40us acquisition deadline unchanged.']),indent=2)+'\n')
if __name__=='__main__':main()
