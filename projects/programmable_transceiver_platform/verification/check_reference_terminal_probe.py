"""Reproduction gate for full reference terminal-current instrumentation."""
import contextlib,io,json,runpy
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE.parent;R=P.parents[1]
with contextlib.redirect_stdout(io.StringIO()):
    shared=runpy.run_path(str(HERE/'check_sar_balance_refinement.py'))
sha=shared['sha'];load=shared['load'];compare=shared['compare']
B=R/'scratch/transceiver-reference-terminal-probe-prepared'
W=R/'scratch/transceiver-reference-terminal-probe'
PB=R/'scratch/transceiver-sar-balance-second-instrumented-prepared'
PW=R/'scratch/transceiver-sar-balance-second-instrumented'
m=json.loads((B/'manifest.json').read_text())
assert sha(PB/'manifest.json')==m['parent_preparation_sha256']
assert sha(PW/'result.json')==m['parent_result_sha256']
for name,h in m['artifacts_sha256'].items():assert sha(B/name)==h
for name,edits in m['buffer_edits'].items():
    original=P/'analog/reference'/name
    assert sha(original)==m['original_buffer_hashes'][name]
    s=(B/name).read_text()
    assert s.count(edits['added'])==1
    s=s.replace(edits['added'],'')
    for old,new in edits['replacements'].items():
        assert s.count(new)==1;s=s.replace(new,old)
    assert s==original.read_text()
assert (B/'adc_reference_pair.spice').read_text().replace('/prepared/','/screen/reference/')==(P/'analog/reference/adc_reference_pair.spice').read_text()
s=(B/'baseline.spice').read_text();extra=' '+' '.join(m['probes'])
for prefix in ('wrdata ','save all'):
    line=next(l for l in s.splitlines() if l.startswith(prefix))
    assert line.endswith(extra);s=s.replace(line,line[:-len(extra)])
s=s.replace('.include /prepared/adc_reference_pair.spice','.include /screen/reference/adc_reference_pair.spice')
assert s==(PB/'baseline.spice').read_text()
if not (W/'result.json').exists():
    print('Exact terminal-probe scope and parent provenance checks pass; terminal results pending.')
else:
    parent=load('sar-balance-second-instrumented');candidate=load('reference-terminal-probe')
    assert sha(PW/'baseline.dat')==m['parent_waveform_sha256']
    assert sha(W/'baseline.spice')==sha(B/'baseline.spice')
    before=parent[2]['sources_before'];after=candidate[2]['sources_before']
    # Only the three explicitly reversed local source copies may differ.
    replaced={'/screen/reference/'+n for n in ('buffer_scaled.spice','buffer_complement.spice','adc_reference_pair.spice')}
    expected={k:v for k,v in before.items() if k not in replaced}
    expected.update({'/prepared/'+n:m['artifacts_sha256'][n] for n in ('buffer_scaled.spice','buffer_complement.spice','adc_reference_pair.spice')})
    assert after==expected
    for probe in m['probes']:assert probe.lower() in candidate[0]
    comparison=compare(parent,candidate)
    report=dict(completed=True,reproduction_pass=comparison['within_10uv_and_decisions'],comparison=comparison,
        waveform_sha256=sha(W/'baseline.dat'),parent_waveform_sha256=sha(PW/'baseline.dat'),
        preparation_sha256=sha(B/'manifest.json'),result_sha256=sha(W/'result.json'),
        checker_sha256=sha(Path(__file__)),comparison_checker_sha256=sha(HERE/'check_sar_balance_refinement.py'),
        limitations=['Reproduction only; full terminal current includes conduction and must not be double-counted.',
                    'Current balance and identification of the earlier residual remain separate checks.'])
    (P/'evidence/reference-terminal-probe.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2))
