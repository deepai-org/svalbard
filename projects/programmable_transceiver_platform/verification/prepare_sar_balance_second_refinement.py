"""Second matched timestep refinement, preserving all circuit and tolerances."""
import hashlib
import json
from pathlib import Path

R = Path(__file__).resolve().parents[3]
P = R/'projects/programmable_transceiver_platform'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

report = P/'evidence/sar-balance-refinement.json'
evidence = json.loads(report.read_text())
assert evidence['completed']
for label in ('baseline', 'instrumented'):
    parent = R/f'scratch/transceiver-sar-balance-refined-{label}-prepared'
    run = R/f'scratch/transceiver-sar-balance-refined-{label}'
    output = R/f'scratch/transceiver-sar-balance-second-{label}-prepared'
    m = json.loads((parent/'manifest.json').read_text())
    result = json.loads((run/'result.json').read_text())
    assert result['returncode'] == 0 and not result['timed_out']
    assert result['sources_before'] == result['sources_after']
    assert sha(run/'baseline.dat') == evidence['waveform_hashes']['fine_'+label]
    assert sha(parent/'baseline.spice') == m['artifacts_sha256']['baseline.spice']
    assert sha(run/'baseline.spice') == sha(parent/'baseline.spice')
    source = (parent/'baseline.spice').read_text()
    old, new = 'tran 5p 209.9n 0 2.5p', 'tran 5p 209.9n 0 1.25p'
    assert source.count(old) == 1
    candidate = source.replace(old,new)
    assert candidate.replace(new,old) == source
    output.mkdir()
    (output/'baseline.spice').write_text(candidate)
    m.update(candidate='Second matched maximum-timestep refinement: '+label,
        parent='sar-balance-refined-'+label,
        parent_preparation_sha256=sha(parent/'manifest.json'),
        parent_result_sha256=sha(run/'result.json'),
        parent_comparison_sha256=sha(report),
        artifacts_sha256={'baseline.spice':sha(output/'baseline.spice')},
        qualification_plan=[
            'Require terminal success, complete finite waveform and unchanged recursive sources.',
            'Keep original10uV cross-deck reproduction criterion and24 full-swing decisions.',
            'Compare each deck against2.5ps parent and prior5ps changes; report decision residues and switching peaks separately.',
            'Compare integrated CDAC charge over fixed external-clock windows, not fitted peak-centered windows.',
            'Report charge sensitivity without declaring a tolerance pass: no physical charge error budget has been established.'],
        charge_windows=dict(start='hold+5*j+2.5ns',end='hold+5*j+3.6ns',
            meaning='UPDATE rising ramp start through UPDATE falling ramp end; includes comparator falling ramp'),
        limitations=['Two step halvings alone do not establish physical accuracy or guarantee asymptotic convergence.'])
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print(output)
