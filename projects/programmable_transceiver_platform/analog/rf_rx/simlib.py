"""ngspice helpers shared by the RF receive testbenches."""
import re
import subprocess
from pathlib import Path

import rfrx_flow as flow

MOS_LINE = re.compile(r'^X(\S+)(\s.*\s)(nfet_03v3|pfet_03v3)(\s.*)?$', re.I)


def ngspice_netlist(text):
    """PDK MOS models are binned .model cards: rewrite X<name> ... nfet_03v3 as M lines."""
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
    dst.write_text(ngspice_netlist(Path(netlist_path).read_text()))
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
