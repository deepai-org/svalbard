"""WR11-4 / DG9-W7GEAR: r7e (grid build, r12/capgrid) full rate (B1=1) at ring 750 MHz with a 125 Mbaud line (6 samples per
symbol, 100BASE-TX raw oversampling, psel odd).  The known full-rate race takes the previous ring cycle's sample on some slots.
For oversampled 125 Mbaud that is harmless only if every captured sample equals the line at its own or an adjacent ring cycle
(transition displaced by <= 1 sample = 1.33 ns of the 8 ns UI).  Reports: exact sample errors, errors not explained by +-1
sample, captured run lengths (must be 5..7 for a 6-sample symbol), word/strobe errors.
  os125.py TAG corner temp vdd psel [words] [neg]"""
import sys, json
from pathlib import Path
import numpy as np
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W))
import capture as c
G = Path('/home/ubuntu/svalbard/scratch/wired_rx/r12/capgrid')
H = Path(__file__).resolve().parent
c.FAST = G / 'fast'; c.GEN = G / 'gen'; c.SCRATCH = H / 'cap'
OS = 6
tag, corner, temp, vdd, psel = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5])
words = int(sys.argv[6]) if len(sys.argv) > 6 else 8
neg = len(sys.argv) > 7 and sys.argv[7] == 'neg'     # negative control: 2-sample displacement must be reported
_p = c.prbs
def prbs_os(n, seed=0x5A):
    s = _p(n // OS + 2, seed)
    return [s[m // OS] for m in range(n)]
c.prbs = prbs_os
r = c.run_bench(tag, 1, ext=True, f=750e6, words=words, psel=psel, corner=corner, temp=temp, vdd=vdd)
# own analysis on the stored waveform: words sampled at WSTB rises (what the macro registers)
d = np.loadtxt(c.SCRATCH / 'sim' / tag / 'out.txt'); t = d[:, 0]
wsv = d[:, 50] > vdd / 2
rises = [t[i] for i in range(1, len(t)) if wsv[i] and not wsv[i - 1]]
sw = [[int(v > vdd / 2) for v in d[int(np.searchsorted(t, x - 20e-12)), 2:22]] for x in rises][3:]
stream = [b for w in sw for b in w]
if neg:   # displace every 6th sample by 2 (a 2-cycle race): must FAIL the +-1 criterion
    stream = [stream[i - 2] if i % 6 == 3 and i >= 2 else b for i, b in enumerate(stream)]
bits = prbs_os(4000)
best = min(((off, sum(bits[off + i] != b for i, b in enumerate(stream))) for off in range(len(bits) - len(stream))), key=lambda x: x[1])
off = best[0]
unexpl = [i for i, b in enumerate(stream) if b != bits[off + i] and not (0 < off + i and (bits[off + i - 1] == b or bits[off + i + 1] == b))]
runs, k = [], 0
for i in range(1, len(stream)):
    k += 1
    if stream[i] != stream[i - 1]:
        runs.append(k); k = 0
runs = runs[1:]
out = dict(tag=tag, corner=corner, temp=temp, vdd=vdd, psel=psel, ring_MHz=750, os=OS, neg=neg, samples=len(stream), strobe_words=len(sw),
           sample_errors=best[1], unexplained_by_1sample=len(unexpl), err_slots=sorted({i % 20 for i, b in enumerate(stream) if b != bits[off + i]}),
           run_min=min(runs) if runs else None, run_max=max(runs) if runs else None,
           pass_125M=bool(len(sw) >= words - 4 and not unexpl and runs and min(runs) >= OS - 1 and max(runs) % OS in (0, 1, OS - 1)),
           flow=dict((k_, r.get(k_)) for k_ in ('bit_errors', 'edge_errors', 'strobe_word_errors', 'word_timing', 'i_mA', 'error')))
res = H / 'results.json'
R = json.loads(res.read_text()) if res.exists() else {}
R[tag] = out; res.write_text(json.dumps(R, indent=1, default=str))
print(json.dumps(out), flush=True)
