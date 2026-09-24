#!/usr/bin/env python3
import hashlib, json
from pathlib import Path
import numpy as np

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load_reference_arrays(roots, records, name):
    arrays = []
    for root, record in zip(roots, records):
        assert record['sources_before'] == record['sources_after']
        c = next((x for x in record['cases'] if x['name'] == name))
        assert c['returncode'] == 0
        for ext, h in c['artifacts_sha256'].items():
            assert sha(root / (name + ext)) == h
        log = (root / (name + '.log')).read_text().lower()
        assert not any((x in log for x in ['warning', 'error', 'aborted']))
        with (root / (name + '.dat')).open() as f:
            h = f.readline().lower().split()
        a = np.loadtxt(root / (name + '.dat'), skiprows=1)
        assert a.shape == (41, len(h)) and np.isfinite(a).all()
        arrays.append((h, a))
    return arrays

def main(hybrid=False):
    R = Path(__file__).resolve().parents[3]
    P = R / 'projects/programmable_transceiver_platform'
    variant = 'hybrid' if hybrid else 'long-mirror'
    W = R / ('scratch/transceiver-reference-pair-' + variant + '-dc')
    B = R / 'scratch/transceiver-reference-pair-device-dc'

    m = json.loads((W / 'change-manifest.json').read_text())
    pair = (P / 'analog/reference/adc_reference_pair_tuned.spice').read_text()
    for file in ('buffer_scaled_tune.spice', 'buffer_complement_tune.spice'):
        cell = (P / 'analog/reference' / file).read_text()
        if hybrid:
            if file == 'buffer_complement_tune.spice':
                assert len(m['changes']) == 5
                for old, new in m['changes']:
                    assert old.split()[0] in ('XIP', 'XIN', 'XT', 'XMP', 'XMN')
                    assert new in (P / 'analog/reference/buffer_scaled_tune.spice').read_text().splitlines()
                    cell = cell.replace(old, new)
        else:
            for old, new in m['changes']:
                cell = cell.replace(old, new)
        pair = pair.replace('.include /screen/reference/' + file, cell)
    records = [json.loads((root / 'result.json').read_text()) for root in (B, W)]
    rows = []
    for name, target in [('VH', 2.15), ('VL', 1.15)]:
        arrays = load_reference_arrays((B, W), records, name)
        expected = (B / (name + '.spice')).read_text().replace('.include /screen/reference/adc_reference_pair_tuned.spice', pair)
        assert expected == (W / (name + '.spice')).read_text()
        (h, b), (ch, c) = arrays
        assert h == ch and np.array_equal(b[:, 0], c[:, 0])
        node = 'v(oh)' if name == 'VH' else 'v(ol)'
        stage = 'xhigh' if name == 'VH' else 'xlow'
        values = []
        for label, a in [('baseline', b), ('candidate', c)]:
            v = dict(zip(h, a[20]))
            stem = f'@m.xdut.{stage}.'
            values.append(dict(
                case=label,
                error_v=float(v[node] - target),
                mirror_current_difference_a=float(v[stem + 'xmn.m0[id]'] - v[stem + 'xmp.m0[id]']),
                tail_margin_v=float(v[stem + 'xt.m0[vds]'] - v[stem + 'xt.m0[vdsat]']),
                **(dict(device_margin_sweep_min_v={dev: float((a[:, h.index(stem + dev + '.m0[vds]')] - a[:, h.index(stem + dev + '.m0[vdsat]')]).min()) for dev in ('xip', 'xin', 'xt', 'xmp', 'xmn', 'xout', 'xload')}) if hybrid else {}),
                supply_power_w=float(-3.3 * v['i(vdd)']),
            ))
        rows.append(dict(rail=name, values=values))
    out = dict(
        **(dict(disposition='Diagnostic candidate only; DC headroom is not dynamic regulation.') if hybrid else {}),
        completed=True,
        exact_declared_changes_verified=True,
        cases=rows,
        provenance=records,
        limitations=['DC only; changed input topology changes internal swing and loop response; compensation and connected dynamics must be rechecked.', 'High input stage changes polarity and bias; device operating points must be checked before dynamic promotion.', 'Ideal target/bias and zero external load remain.'] if hybrid else ['DC only; longer/wider devices increase capacitance and area; compensation and connected dynamics must be rechecked.', 'Changing length affects more than output resistance; not a unique causal proof.', 'Ideal target/bias and zero external load remain.'],
    )
    (P / ('evidence/reference-' + variant + '.json')).write_text(json.dumps(out, indent=2) + '\n')
    print(rows)
if __name__ == '__main__':
    main()
