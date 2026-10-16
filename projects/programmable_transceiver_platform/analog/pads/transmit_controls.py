"""Generic wired-TX mode interlock at the serializer/bias boundary.

Branch requests are 0/1 levels; termination/reset/qualification are 3.3V logic.
This is a behavioral contract, not implemented glitch-free transistor control.
"""
import json
from design import PROJECT

BRANCHES = ('MAIN', 'POST', 'TMDS', 'DETECT')
CONFLICTS = (('TMDS', 'MAIN'), ('TMDS', 'POST'), ('TMDS', 'DETECT'),
             ('TMDS', 'TERM'), ('DETECT', 'MAIN'), ('DETECT', 'POST'),
             ('DETECT', 'TERM'))


def attach(deck, reset_source, qualified_source):
    low, high = json.loads((PROJECT/'spec/analog-architecture.json').read_text())['blocks']['monitor']['parameters']['supply_window_v']
    for branch in BRANCHES:
        original = f'VEN_{branch} EN_{branch} 0 '
        if deck.count(original) != 1:
            raise ValueError('Expected branch request: ' + branch)
        deck = deck.replace(original, f'VEN_{branch} REQ_EN_{branch} 0 ')
    original = 'VTERM_ENABLE TERM_ENABLE 0 '
    if deck.count(original) != 1:
        raise ValueError('Expected termination request')
    deck = deck.replace(original, 'VTERM_ENABLE REQ_TERM_ENABLE 0 ')
    requests = {branch: f'(V(REQ_EN_{branch})>.5)' for branch in BRANCHES}
    requests['TERM'] = '(V(REQ_TERM_ENABLE)>1.65)'
    conflicts = '+'.join(f'({requests[a]}*{requests[b]})' for a, b in CONFLICTS)
    deck += f'BTX_CONFLICT TX_CONFLICT 0 V=({conflicts}>0)\n'
    deck += f'VTX_RESET TX_RESET 0 {reset_source}\nVTX_QUALIFIED TX_QUALIFIED 0 {qualified_source}\n'
    deck += (f'BTX_VALID TX_VALID 0 V=(V(VDD)>={low})*(V(VDD)<={high})*'
             '(V(TX_RESET)<1.65)*(V(TX_QUALIFIED)>1.65)*(V(TX_CONFLICT)<.5)\n')
    for branch in BRANCHES:
        deck += f'BTX_{branch} EN_{branch} 0 V=V(TX_VALID)*{requests[branch]}\n'
    deck += 'BTX_TERM TERM_ENABLE 0 V=V(VDD)*V(TX_VALID)*(V(REQ_TERM_ENABLE)>1.65)\n'
    return deck
