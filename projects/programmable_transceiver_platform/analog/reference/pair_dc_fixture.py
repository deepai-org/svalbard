"""Common reference-pair bias fixture; circuit alternatives stay in their runners."""
import hashlib,re,subprocess
from pathlib import Path

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

body = '.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice\n.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical\n.include /screen/reference/adc_reference_pair_tuned.spice\n.temp 27\nVDD VDD 0 3.3\nVH HIGH 0 2.15\nVL LOW 0 1.15\nIBN VDD BN 20u\nIBP BP 0 20u\nXBN BN BN 0 0 nfet_03v3 w=8u l=.5u\nXBP BP BP VDD VDD pfet_03v3 w=8u l=.5u\nXDUT HIGH LOW OH OL BN BP VDD 0 pt_adc_reference_pair_tuned\n'

def source_hashes(text, parent):
    paths = {}

    def scan(text, parent):
        for line in text.splitlines():
            m = re.match('\\s*\\.(?:include|lib)\\s+(\\S+)', line, re.I)
            if not m:
                continue
            q = Path(m[1].strip(chr(34) + chr(39)))
            q = q if q.is_absolute() else parent / q
            if not q.is_file():
                assert line.lower().lstrip().startswith('.lib ') and len(line.split()) == 2
                continue
            q = q.resolve()
            if str(q) not in paths:
                paths[str(q)] = sha(q)
                scan(q.read_text(), q.parent)
    scan(text, parent)
    paths[str(Path(__file__))] = sha(Path(__file__))
    return paths

def device_probes():
    probes = [f'v(XDUT.{stage}.{node})' for stage in ('XHIGH', 'XLOW') for node in ('A', 'X', 'T')]
    probes += [f'@m.xdut.{stage}.{dev}.m0[{q}]' for stage in ('xhigh', 'xlow') for dev in ('xip', 'xin', 'xt', 'xmp', 'xmn', 'xout', 'xload') for q in ('vds', 'vdsat', 'id', 'gm', 'gds')]
    return probes

def sweep_targets(body, probes, O):
    rows = []
    for name, target in [('VH', 2.15), ('VL', 1.15)]:
        d = '* Paired reference target response\n' + body + f'.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nsave all {' '.join(probes)}\ndc {name} {target - 0.02:.6f} {target + 0.02:.6f} .001\nwrdata /work/{name}.dat v(HIGH) v(LOW) v(OH) v(OL) v(BN) v(BP) i(VDD) {' '.join(probes)}\n.endc\n.end\n'
        p = O / (name + '.spice')
        p.write_text(d)
        h = sha(p)
        with (O / (name + '.log')).open('w') as log:
            q = subprocess.run(['ngspice', '-b', str(p)], stdout=log, stderr=subprocess.STDOUT, timeout=60)
        assert sha(p) == h
        rows.append(dict(name=name, target_v=target, returncode=q.returncode, artifacts_sha256={e: sha(O / (name + e)) for e in ('.spice', '.dat', '.log') if (O / (name + e)).exists()}))
    return rows
