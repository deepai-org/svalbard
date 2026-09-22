"""Reproducible detector-circuit and connected-control integration checks."""
import importlib,json,hashlib
from chip_model import P

CHECKS=(
 ('load_screen','receiver-detect-load-screen.json'),
 ('timing_screen','receiver-detect-timing-screen.json'),
 ('release_screen','receiver-detect-release-screen.json'),
 ('energy_screen','receiver-detect-energy-screen.json'),
 ('probe_sequence','receiver-detect-sequence-screen.json'),
 ('rearm_screen','receiver-detect-rearm-screen.json'),
 ('chip_adapter','receiver-detect-chip-adapter.json'),
 ('managed_adapter','receiver-detect-managed-adapter.json'),
 ('resource_adapter','receiver-detect-resource-adapter.json'),
)

def main():
    rows=[]
    for module,name in CHECKS:
        importlib.import_module('receiver_detect_'+module).main()
        p=P/'evidence'/name;report=json.loads(p.read_text());assert report['status']=='passed'
        rows.append(dict(module=module,evidence=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    report=dict(status='passed',checks=rows,complete_architecture=False,physical_qualification=False,
        limitations=['ReceiverDetect resource adapter is a connected model variant, not yet the default combined profile.',
        'Supply loading is quantified separately but not coupled to chip rails; no electrical-coexistence qualification.',
        'Known small-coupling-capacitor false negatives remain outside the declared load envelope.',
        'Provisional detector resource and management ABI; full uncertainty and physical device/package validation remain open.'])
    (P/'evidence/connected-receiver-detection.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed all nine receiver-detection circuit/control screens; supply integration remains open')

if __name__=='__main__':main()
