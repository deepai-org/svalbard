"""Parallel phase-history requirement model, independent of protocol syntax.

Input rows are eight real sample observations per local UI. This reduction
checks phase choice and history reconstruction; it does not generate analog
samples, simulate metastability, or replace subsequent tracking CDR.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseChoice:
    phase: int
    seed32: int
    margin_ui: float
    transitions: int


def select_phase(rows, *, minimum_edges=4, required_margin_ui=.25):
    if len(rows)<4 or len(rows)>16:
        raise ValueError('acquisition window must be4..16UI')
    if type(minimum_edges) is not int or not 1<=minimum_edges<=8:
        raise ValueError('invalid edge count')
    if not 0 < required_margin_ui < .5:
        raise ValueError('invalid sample margin')
    flat=[]
    for row in rows:
        if len(row)!=8 or any(type(x) is not int or x not in (0,1) for x in row):
            raise ValueError('eight binary observations per UI required')
        flat.extend(row)
    # Each changed pair brackets an edge: retain the whole uncertainty interval.
    edges=[((i%8)-.5)/8 % 1 for i in range(1,len(flat)) if flat[i]!=flat[i-1]]
    if len(edges)<minimum_edges:
        raise ValueError('insufficient transition evidence')
    def separation(a,b):
        d=abs(a-b)
        return min(d,1-d)
    margins=[min(separation(p/8,e)-1/16 for e in edges) for p in range(8)]
    best=max(range(8),key=lambda p:margins[p])
    if margins[best] < required_margin_ui:
        raise ValueError('no safe phase across observed edges')
    return PhaseChoice(best,best*4,margins[best],len(edges))


class PhaseHistory:
    """Bounded circular storage; consumed rows may roll out, needed rows may not."""
    def __init__(self, capacity_ui=32):
        if type(capacity_ui) is not int or capacity_ui<16:
            raise ValueError('insufficient phase history')
        self.capacity=capacity_ui
        self.rows={}
        self.write_index=0
        self.read_index=None
        self.phase=None
        self.acknowledged=False
        self.live_next=None

    def append(self,row):
        row=tuple(row)
        if len(row)!=8 or any(type(x) is not int or x not in (0,1) for x in row):
            raise ValueError('invalid phase samples')
        oldest=self.write_index-self.capacity
        if self.read_index is not None and oldest>=self.read_index:
            raise BufferError('unread phase history would be overwritten')
        self.rows.pop(oldest,None)
        self.rows[self.write_index]=row
        self.write_index+=1

    def acquire(self,start_index,window_ui=8):
        if self.read_index is not None or self.live_next is not None:
            raise ValueError('cannot reseed active replay')
        if any(i not in self.rows for i in range(start_index,start_index+window_ui)):
            raise ValueError('required early history unavailable')
        choice=select_phase([self.rows[i] for i in range(start_index,start_index+window_ui)])
        self.phase=choice.phase
        self.read_index=start_index
        self.acknowledged=False
        return choice

    def acknowledge(self,seed32):
        if self.phase is None or self.acknowledged or seed32!=self.phase*4:
            raise ValueError('stale or mismatched phase acknowledgment')
        self.acknowledged=True

    def handoff(self,next_live_index):
        if not self.acknowledged or self.read_index!=self.write_index or next_live_index!=self.read_index:
            raise ValueError('handoff must follow every retained bit exactly once')
        self.live_next=next_live_index
        self.read_index=None

    def live(self,index,bit):
        if self.live_next is None or index!=self.live_next or type(bit) is not int or bit not in (0,1):
            raise ValueError('live stream index discontinuity')
        self.live_next+=1
        return index,bit

    def replay(self,maximum=2):
        if type(maximum) is not int or not 1<=maximum<=2 or self.read_index is None or not self.acknowledged:
            raise ValueError('replay requires acquisition and rate<=2bits/UI')
        out=[]
        while len(out)<maximum and self.read_index<self.write_index:
            index=self.read_index
            out.append((index,self.rows[index][self.phase]))
            self.read_index+=1
        return out
