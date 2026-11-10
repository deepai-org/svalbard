#!/usr/bin/env python3
"""Device-level LVS of the routed core-bias assembly.

Layout: Magic flat extraction of the COMPLETE routed GDS of a routing run
(every master's devices included, nothing abstracted). Reference: the
generated pt_core_bias top cell with SCHEMATIC leaf netlists
(core_bias_routing/device_lvs_reference.py); nothing is derived from the
routed layout. Three negative controls must each be rejected: a reference
with one instance net exchanged, a reference with two consumers' bank outputs
exchanged, and the routed GDS with a VDD-VSS Metal3 bridge.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
FLOW = Path(__file__).resolve().parent/'core_bias_routing'
sys.path.insert(0, str(FLOW))
import device_lvs_reference as reference  # noqa: E402

IMAGE = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
AVALON = ROOT/'scratch/core_support/avalon_lib'
NEGATIVES = {
    'reference_neg.spice': dict(instance='Xbank_conv', a='BANK_EN_adc_i', b='BIAS_adc_i'),
    'reference_neg_swap.spice': dict(instance='Xbank_rf', a='BIAS_lna', b='BIAS_rxmix_i'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def latest_routing():
    runs = sorted(p for p in (ROOT/'scratch').glob('core-bias-routing-2*') if p.is_dir())
    passing = [p for p in runs if (p/'report.json').exists() and
               json.loads((p/'report.json').read_text()).get('status') == 'pass']
    assert passing, 'No passing core-bias routing run'
    return passing[-1]


def property_errors(text):
    """Parse netgen property errors. Only a MIM capacitor whose c_width and
    c_length are transposed (identical area and perimeter, same capacitance)
    is accepted; netgen's GF180 setup does not symmetrize these two."""
    errors = []
    for m in re.finditer(r'^(\S+) vs\. (\S+):\n((?: [^\n]*\n)+)', text, re.M):
        values = {p: (float(a), float(b)) for p, a, b in
                  re.findall(r'^ (\S+) circuit1: (\S+)\s+circuit2: (\S+)', m[3], re.M)}
        transposed = (set(values) == {'c_length', 'c_width'} and m[1].startswith('cap_mim') and
                      values['c_length'][0] == values['c_width'][1] and values['c_width'][0] == values['c_length'][1])
        errors.append(dict(layout=m[1], reference=m[2], values=values, accepted_transposed_mim=transposed))
    return errors


def final(path):
    text = Path(path).read_text(errors='replace') if Path(path).exists() else ''
    lines = [l.strip() for l in text.splitlines() if l.startswith('Final result')]
    counts = re.findall(r'Number of (devices|nets): (\d+)[^|]*\|Number of \1: (\d+)', text)
    failures = [f for f in ('failed pin matching', 'Top level cell failed', 'Netlists do not match')
                if f in text]
    return dict(final=lines[-1] if lines else None,
                match='Final result: Circuits match uniquely.' in text and not failures,
                failure_strings=failures,
                property_errors_reported='Property errors were found' in text,
                property_errors=property_errors(text),
                top_counts=[dict(kind=k, layout=int(a), reference=int(b)) for k, a, b in counts[-2:]])


def feedback(path):
    text = Path(path).read_text() if Path(path).exists() else ''
    kinds = re.findall(r'feedback add "([^;"]*)', text)
    nodes = re.findall(r'connecting remainder to node (\S+?)"', text)
    return dict(items=len(kinds), kinds={k: kinds.count(k) for k in set(kinds)},
                missing_terminal_nodes={n: nodes.count(n) for n in set(nodes)})


def missing_terminal_devices(layout_text):
    """Classify the devices behind Magic's 'device missing 1 terminal;
    connecting remainder to node' feedback. Magic writes such a MOS with a
    zero source area (as=0) after tying the missing terminal to the remaining
    diffusion node, and such a resistor with both ends on one node. That is
    harmless only if the channel (or body of the resistor) connects no two
    distinct nets: drain == source. Anything else is reported as suspect."""
    text = re.sub(r'\n\+\s*', ' ', layout_text)
    rows, suspect = {}, []
    for line in text.splitlines():
        f = line.split()
        if not f or f[0][0] not in 'Xx':
            continue
        model = next((x for x in f if re.match(r'(nfet|pfet|ppolyf|pplus|nplus)', x)), None)
        if model is None:
            continue
        nodes = f[1:f.index(model)]
        if model.startswith(('nfet', 'pfet')):
            if not re.search(r'\bas=0\s', line+' '):
                continue
            kind = ('dummy: all terminals one node' if len(set(nodes)) == 1 else
                    'MOS capacitor: drain=source=body' if nodes[0] == nodes[2] == nodes[3] else
                    'drain=source, body separate' if nodes[0] == nodes[2] else 'SUSPECT: drain != source')
        else:
            if nodes[0] != nodes[1]:
                continue
            kind = 'resistor dummy: both ends one node'
        key = f'{model} | {kind}'
        rows[key] = rows.get(key, 0)+1
        if kind.startswith('SUSPECT'):
            suspect.append(line[:200])
    return dict(classes=rows, total=sum(rows.values()), suspect=suspect)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--routing-dir', type=Path)
    ap.add_argument('--output-dir', type=Path, default=ROOT/'scratch/core-bias-device-lvs')
    a = ap.parse_args()
    routing = (a.routing_dir or latest_routing()).resolve()
    routing_report = json.loads((routing/'report.json').read_text())
    inp = Path(routing_report['input'])
    out = a.output_dir.resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(dict(status='incomplete'))+'\n')
    extracted = inp/'pt_core_bias.spice'
    assert sha(extracted) == routing_report['input_hashes']['pt_core_bias.spice'], 'Routing input netlist changed'
    shutil.copy(routing/'pt_core_bias_routed.gds', out)
    shutil.copy(routing/'routed.json', out)
    built = reference.build(extracted, out/'reference.spice')
    negatives = {name: reference.build(extracted, out/name, mutate) for name, mutate in NEGATIVES.items()}
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--user', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp',
           '-e', 'PDK=gf180mcuD', '-e', 'PDK_ROOT=/foss/pdks', '-e', 'PDKPATH=/foss/pdks/gf180mcuD',
           '-v', f'{out}:/work', '-v', f'{FLOW}:/flow:ro', '--mount',
           f'type=bind,src={AVALON},dst=/foss/pdks/gf180mcuD/libs.ref/gf180mcu_as_sc_mcu7t3v3,readonly',
           '--entrypoint', '/bin/bash', IMAGE, '-lc', 'bash /flow/device_lvs.sh']
    with open(out/'run.log', 'w') as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=3600).returncode
    assert rc == 0, (out/'run.log').read_text()[-3000:]
    alias = int((out/'pnp_alias_count.txt').read_text().strip() or 0)
    layout = (out/'layout_flat.spice').read_text()
    reference_pnps = sum(int(m or 1) for m in re.findall(
        r'^X\S+ .*pnp_05p00x05p00(?: m=(\d+))?', (out/'reference.spice').read_text(), re.M))
    main_result = final(out/'lvs_device.out')
    negative_results = {name: final(out/(name.replace('reference', 'lvs_device').replace('.spice', '.out')))
                        for name in NEGATIVES}
    negative_results['layout_vdd_vss_bridge'] = final(out/'lvs_device_neg_layout.out')
    checks = dict(
        match=main_result['match'],
        # Every reported property error must be parsed and be a transposed MIM.
        properties=(not main_result['property_errors_reported'] or
                    (bool(main_result['property_errors']) and
                     all(e['accepted_transposed_mim'] for e in main_result['property_errors']))),
        negatives_rejected=all(r['final'] and not r['match'] for r in negative_results.values()),
        # The alias may only cover the bandgap's 9 misrecognized PNP array
        # cells: bounded by the reference's PNP device count.
        pnp_alias_bounded=0 < alias <= reference_pnps and alias == 9,
        no_parasitic_capacitors_in_reference=not re.search(r'^C', (out/'reference.spice').read_text(), re.M),
    )
    # Every 'device missing 1 terminal' feedback item must be a device whose
    # drain and source (resistor ends) are one node; the counts must agree.
    fb = feedback(out/'extract_feedback.txt')
    missing = missing_terminal_devices(layout)
    checks['missing_terminal_devices_harmless'] = (
        not missing['suspect'] and missing['total'] == fb['kinds'].get('device missing 1 terminal', 0))
    report = dict(
        status='pass' if all(checks.values()) else 'fail',
        scope='device-level LVS: flat Magic extraction of the complete routed core-bias GDS vs schematic-leaf reference',
        routing_run=str(routing.relative_to(ROOT)),
        routed_gds_sha256=sha(out/'pt_core_bias_routed.gds'),
        checks=checks, result=main_result, negative_controls=negative_results,
        reference=built, negative_references={k: v['mutation'] for k, v in negatives.items()},
        layout_device_lines=len(re.findall(r'^X', layout, re.M)), layout_diodes=len(re.findall(r'^D', layout, re.M)),
        pnp_alias=dict(rule='pnp_10p00x00p42 -> pnp_05p00x05p00 (layout side, as qualified core-support bandgap LVS)',
                       aliased_devices=alias, reference_pnp_devices=reference_pnps),
        extraction_feedback=fb, missing_terminal_devices=missing,
        image=IMAGE, flow_hashes={p.name: sha(p) for p in sorted(FLOW.glob('device_lvs*'))},
        script_sha256=sha(__file__),
        not_covered=['Magic device recognition is trusted (same deck as every block LVS)'])
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(status=report['status'], checks=checks, result=main_result['final'],
                          negatives={k: v['final'] for k, v in negative_results.items()}), indent=2))
    if report['status'] != 'pass':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
