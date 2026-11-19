"""ngspice helpers shared by the RF receive testbenches."""
import re
import subprocess
from pathlib import Path

import rfrx_flow as flow

MOS_LINE = re.compile(r'^X(\S+)(\s.*\s)(nfet_03v3|pfet_03v3)(\s.*)?$', re.I)


def ngspice_netlist(text):
    """Netlist as handed to ngspice.  Round 3 (coordinator ruling): X instances of nfet_03v3 / pfet_03v3 are KEPT.  The corner libraries
    load the PDK `fets_mm` wrappers (subckt nfet_03v3 ... -> m0 with delvto / mulu0 from agauss, gated by sw_stat_mismatch), so X
    instances carry mismatch in Monte Carlo and are identical to the bare model at sw_stat_mismatch = 0.  The old rewrite to M lines
    (kept as ngspice_netlist_mline for comparison) bypassed the wrappers: Monte Carlo on it shows no mismatch (mc_selftest.py)."""
    return text if text.endswith('\n') else text + '\n'


def ngspice_netlist_mline(text):
    """Pre-round-3 behaviour: rewrite X<name> ... nfet_03v3 as M lines (bypasses the PDK mismatch wrappers)."""
    out = []
    for line in text.splitlines():
        m = MOS_LINE.match(line)
        if m:
            line = f'M{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4) or ""}'
        out.append(line)
    return '\n'.join(out) + '\n'


def prepare(work, netlist_path, name):
    work.mkdir(parents=True, exist_ok=True)
    dst = work / name
    text = ngspice_netlist(Path(netlist_path).read_text())
    if not (dst.exists() and dst.read_text() == text):
        # write-then-rename: parallel benches sharing this file never read a half-written netlist
        import os, threading
        tmp = work / f'.{name}.{os.getpid()}.{threading.get_ident()}.tmp'
        tmp.write_text(text)
        os.replace(tmp, dst)
    return dst.name


def run(work, deck_name, body, *, corner='typical', temp=27, timeout=3600):
    deck = f'* {deck_name}\n' + flow.sim_header(corner, temp) + body + '\n.end\n'
    (work / deck_name).write_text(deck)
    log = flow.ngspice(work, deck_name, timeout=timeout)
    return log, flow.parse_meas(log)


def read_table(path):
    """Read an ngspice wrdata file into columns (x, y pairs flattened)."""
    rows = []
    for line in Path(path).read_text().splitlines():
        try:
            rows.append([float(v) for v in line.split()])
        except ValueError:
            pass
    return rows


CORNERS = [(c, t, v) for c in ('typical', 'ss', 'ff') for t in (22, 32) for v in (3.15, 3.35)]
# sf / fs added (flow.sim_header supports them: MOS skew with typical R / MIM).  CORNERS stays the 12-point tt/ss/ff list the
# published bbfilter evidence was swept on; CORNERS_5P is the 20-point list (the same as lna_close.CORNERS).
CORNERS_5P = [(c, t, v) for c in ('typical', 'ss', 'ff', 'sf', 'fs') for t in (22, 32) for v in (3.15, 3.35)]
