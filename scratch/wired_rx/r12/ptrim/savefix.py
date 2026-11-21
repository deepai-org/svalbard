"""Wrap r10ptrim bench.deck so ngspice keeps only the written vectors (`save` before `tran`): the flat R+C netlist (~11 k
resistors per copy) otherwise exhausts memory.  Import after bench; patches bench.deck in place."""
import re
import bench
_deck = bench.deck


def deck(*a, **k):
    text, meta = _deck(*a, **k)
    m = re.search(r'^wrdata out\.txt (.*)$', text, re.M)
    vecs = ' '.join(x for x in m.group(1).split())
    text = text.replace('.control\ntran', f'.control\nsave {vecs}\ntran', 1)
    assert f'save {vecs}' in text
    return text, meta


bench.deck = deck
