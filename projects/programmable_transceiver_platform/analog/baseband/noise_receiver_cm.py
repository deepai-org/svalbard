"""Stationary filter noise diagnostic with resistor calibration; not mixer noise."""
import hashlib, json, re, subprocess, sys
from pathlib import Path

def main(large_input=False, *, entrypoint=None):
    CONTRIBUTORS = '--contributors' in sys.argv
    O = Path('/work')

    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()
    base = '.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice\n.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical\n.include /screen/bb_filter_section.spice\n.temp 27\n'
    paths = {Path(__file__), Path(entrypoint or __file__)}

    def deps(text, parent):
        for line in text.splitlines():
            m = re.match('\\s*\\.(?:include|inc|lib)\\s+(\\S+)', line, re.I)
            if not m:
                continue
            p = Path(m[1].strip('"\''))
            p = p if p.is_absolute() else parent / p
            if not p.is_file():
                assert line.lower().lstrip().startswith('.lib ') and len(line.split()) == 2
                continue
            p = p.resolve()
            if p not in paths:
                paths.add(p)
                deps(p.read_text(), p.parent)
    deps(base, O)
    before = {str(p): sha(p) for p in sorted(paths)}
    excerpts = []
    for p in sorted(paths):
        for number, line in enumerate(p.read_text().splitlines(), 1):
            if re.search('fnoicor|(?:^|\\s)(?:fnoimod|tnoimod|noia|noib|noic|ef)\\s*=', line, re.I):
                excerpts.append(dict(path=str(p), line=number, text=line))
    (O / 'model-noise-lines.json').write_text(json.dumps(excerpts, indent=2) + '\n')
    rows = []
    for name, corner in [('resistor', None), ('filter_f0', 0), ('filter_f1', 1)]:
        if corner is None:
            circuit = 'VS SIG 0 DC 0 AC 1\nRTEST SIG OP 1000\n'
            output = 'v(OP)'
        else:
            circuit = f'.param fnoicor={corner}\nVDD VDD 0 3.3\nVB BIAS 0 2.25\nVCM CM 0 1.177\nVS SIG 0 DC 0 AC 1\nEP SP CM SIG 0 .5\nEN SN CM SIG 0 -.5\nRP SP IP 1000\nRN SN IN 1000\nXDUT IP IN OP ON BIAS VDD 0 pt_bb_filter RFB=20k C=20p\n'
            output = 'v(OP,ON)'
        control = f'.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nnoise {output} VS dec 40 1k 100meg\nsetplot noise1\nwrdata /work/{name}.dat onoise_spectrum inoise_spectrum\nsetplot noise2\nwrdata /work/{name}-integrated.dat onoise_total inoise_total\n.endc\n.end\n'
        if CONTRIBUTORS:
            control = control.replace('dec 40 1k 100meg\n', 'dec 40 1k 100meg 1\n').replace(f'wrdata /work/{name}.dat onoise_spectrum inoise_spectrum', f'wrdata /work/{name}.dat onoise_spectrum inoise_spectrum\nwrdata /work/{name}-contributors.dat all')
        d = '* Stationary noise diagnostic\n' + base + circuit + control
        if large_input:
            if corner is not None:
                gain = Path('/screen/bb_pmos_gain.spice').read_text()
                candidate = gain.replace('pt_bb_pmos_gain', 'pt_bb_pmos_gain_large_input')
                for line in gain.splitlines():
                    if line.startswith(('XIP ', 'XIN ')):
                        assert 'w=4u l=0.28u' in line
                        candidate = candidate.replace(line, line.replace('w=4u l=0.28u', 'w=8u l=0.56u'))
                cell = Path('/screen/bb_filter_section.spice').read_text()
                assert cell.count('XA GP GN MP MN T1 BIAS VDD pt_bb_pmos_gain') == 1
                cell = cell.replace('XA GP GN MP MN T1 BIAS VDD pt_bb_pmos_gain', 'XA GP GN MP MN T1 BIAS VDD pt_bb_pmos_gain_large_input')
                d = d.replace('.include /screen/bb_filter_section.spice', candidate + cell)
        p = O / (name + '.spice')
        p.write_text(d)
        h = sha(p)
        with (O / (name + '.log')).open('w') as f:
            s = subprocess.run(['ngspice', '-b', str(p)], stdout=f, stderr=subprocess.STDOUT, timeout=60)
        assert sha(p) == h
        rows.append(dict(name=name, fnoicor=corner, returncode=s.returncode, artifacts_sha256={e: sha(O / (name + e)) for e in (('.spice', '.log', '.dat', '-integrated.dat', '-contributors.dat') if CONTRIBUTORS else ('.spice', '.log', '.dat', '-integrated.dat')) if (O / (name + e)).exists()}))
    after = {str(p): sha(p) for p in sorted(paths)}
    assert before == after
    (O / 'result.json').write_text(json.dumps(dict(cases=rows, source_sha256_before=before, source_sha256_after=after, model_excerpts_sha256=sha(O / 'model-noise-lines.json')), indent=2) + '\n')
    print([(c['name'], c['returncode']) for c in rows])

if __name__ == "__main__":
 main()
