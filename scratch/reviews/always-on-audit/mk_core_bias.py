#!/usr/bin/env python3
"""Regenerate the audit copies of the assembled bias netlist (not committed: 1.4 MB each).

bias/pt_core_bias.spice : integration/core_bias.py build() text (C-only extracted bandgap/biasgen + distribution)
bias2/models.spice      : the same text without the pt_core_bias top subckt (for the stand-alone decks)
Run on the host before `gen.py bias`.
"""
import sys
from pathlib import Path
W = Path(__file__).resolve().parent
P = W.parents[2] / 'projects/programmable_transceiver_platform'
sys.path[:0] = [str(P / 'verification'), str(P / 'integration')]
import core_bias  # noqa: E402
text = core_bias.build(lambda p: Path(p).read_text())['text']
(W / 'bias').mkdir(exist_ok=True)
(W / 'bias2').mkdir(exist_ok=True)
(W / 'bias' / 'pt_core_bias.spice').write_text(text)
(W / 'bias2' / 'models.spice').write_text(text[:text.index('.subckt pt_core_bias')])
print('written', len(text))
