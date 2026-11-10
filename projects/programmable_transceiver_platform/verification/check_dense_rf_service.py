#!/usr/bin/env python3
"""Check both RF directions at 40 MS/s through the complete paired RTL core."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from stream_codec import unprotect

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]


def check(out, burst=False):
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text('{"status":"incomplete"}\n')
    samples = [((i*123457+0xabc123) ^ (i << 7)) & 0xffffff for i in range(10000)]
    sources = [PROJECT/'sim/tb_dense_rf_service.sv']+[PROJECT/'rtl'/name for name in
               ['pt_core.sv', 'pt_core_pair.sv', 'pt_pair_gearbox.sv', 'pt_dense_pair.sv',
                'pt_dense_pair_link.sv', 'pt_dense_header.sv', 'pt_fifo.sv']]+[PROJECT/'sim/reference/pt_dense_transport.sv']
    checked_sources = sources+[Path(__file__).resolve(),
                               PROJECT/'verification/stream_codec.py', PROJECT/'verification/transport_model.py']
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in checked_sources}
    cases = []
    for mode in (0, 1):
        width = 16 if mode else 24
        bits = []
        for sample in samples:
            compressed = ((sample >> 16) << 8 | ((sample >> 4) & 255)) if mode else sample
            bits.extend((compressed >> bit) & 1 for bit in range(width))
        words = [sum(bit << position for position, bit in enumerate(bits[start:start+10]))
                 for start in range(0, len(bits)-9, 10)]
        for phase in (0, .7, 6.2, 12.4, 24.1):
            case = out/f'mode-{mode}-phase-{phase}'
            case.mkdir(exist_ok=True)
            (case/'samples.hex').write_text(''.join(f'{value:06x}\n' for value in samples))
            (case/'words.hex').write_text(''.join(f'{value:03x}\n' for value in words)+
                                          '000\n'*(24000-len(words)))
            subprocess.run(['iverilog', '-g2012', '-I', str(PROJECT/'rtl'), '-s', 'tb_dense_rf_service',
                            '-P', f'tb_dense_rf_service.MODE8={mode}', '-P', f'tb_dense_rf_service.RF_PHASE={phase}',
                            '-P', f'tb_dense_rf_service.HOST_BURST={int(burst)}',
                            '-o', str(case/'bench.vvp'), *map(str, sources)], check=True, capture_output=True)
            run = subprocess.run(['vvp', str(case/'bench.vvp')], cwd=case, capture_output=True, text=True)
            (case/'simulation.log').write_text(run.stdout+run.stderr)
            assert run.returncode == 0 and 'DENSE_RF_PASS' in run.stdout, (case, run.stdout, run.stderr)
            full = 0
            if burst:
                stream = [int(word, 16) for word in (case/'h2d-words.txt').read_text().split()]
                assert stream[:8] == [0x3a5,0x05a,0x2d3,0x12c,0x369,0x096,0x21e,0x1e1]
                for start in range(8, len(stream)-63, 64):
                    metadata = unprotect(sum(stream[start+i] << (10*i) for i in range(4)))
                    assert stream[start+4] == 0x2d3
                    full += int((metadata >> 6) & 63 == 59)
                assert full > 0, 'No actual full-quota host frame exercised'
            cases.append(dict(mode8=mode, rf_phase_ns=phase, full_quota_host_frames=full, result=run.stdout.strip()))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items()), 'Sources changed during run'
    result = dict(status='pass', sample_rate_msps=40, host_word_mhz=312.5, duration_us=200, startup_full_frame_burst=burst, cases=cases,
                  scope='paired-core functional RF service; no physical timing, pad or analog chain closure',
                  source_hashes=hashes)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_hashes'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/dense-rf-service')
    parser.add_argument('--burst', action='store_true')
    args = parser.parse_args()
    check(args.output_dir.resolve(), args.burst)
