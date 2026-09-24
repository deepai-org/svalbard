"""Small target perturbations of actual tuned reference pair, zero external DC load."""
import json
from pathlib import Path
from pair_dc_fixture import body as fixture_body, sha, source_hashes, device_probes, sweep_targets

def main(variant='long_mirror', entrypoint=None):
    if variant == 'long_mirror':
        devices = ('XMP ', 'XMN ')
        high_only = False
        expected = 'w=8u l=.5u'
        replacement = 'w=16u l=1u'
        count = 4
    elif variant == 'wide_input':
        devices = ('XIP ', 'XIN ')
        high_only = True
        expected = 'w=8u l=.5u'
        replacement = 'w=16u l=.5u'
        count = 2
    elif variant == 'half_tail':
        devices = ('XT ',)
        high_only = True
        expected = 'm={16*S}'
        replacement = 'm={8*S}'
        count = 1
    else:
        raise ValueError(variant)
    body = fixture_body
    O = Path('/work')
    paths = source_hashes(body, O)
    paths[str(Path(__file__))] = sha(Path(__file__))
    if entrypoint is not None:
        paths[str(Path(entrypoint))] = sha(Path(entrypoint))
    pair = Path('/screen/reference/adc_reference_pair_tuned.spice').read_text()
    expanded = pair
    changes = []
    for filename in ('buffer_scaled_tune.spice', 'buffer_complement_tune.spice'):
        p = Path('/screen/reference') / filename
        cell = p.read_text()
        changed = cell
        for line in cell.splitlines():
            if (not high_only or filename == 'buffer_complement_tune.spice') and line.startswith(devices):
                assert expected in line
                new = line.replace(expected, replacement)
                changed = changed.replace(line, new)
                changes.append((line, new))
        assert expanded.count('.include /screen/reference/' + filename) == 1
        expanded = expanded.replace('.include /screen/reference/' + filename, changed)
    assert len(changes) == count
    body = body.replace('.include /screen/reference/adc_reference_pair_tuned.spice', expanded)
    (O / 'change-manifest.json').write_text(json.dumps(dict(changes=changes, scope={'long_mirror': 'Only four mirror FET W/L pairs doubled; all multiplicities, targets, biases and compensation retained.', 'wide_input': 'Only high-reference input-pair widths doubled; lengths, multiplicities, output stage, biases and compensation retained.', 'half_tail': 'Only high-reference tail multiplicity halved; input and output geometry, biases and compensation retained.'}[variant]), indent=2) + '\n')
    probes = device_probes()
    rows = sweep_targets(body, probes, O)
    assert paths == {n: sha(Path(n)) for n in paths}
    (O / 'result.json').write_text(json.dumps(dict(cases=rows, sources_before=paths, sources_after=paths), indent=2) + '\n')
    print([(r['name'], r['returncode']) for r in rows])
if __name__ == '__main__':
    main()
