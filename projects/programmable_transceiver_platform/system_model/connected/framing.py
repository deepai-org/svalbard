"""Experimental marker framing; no protocol-specific alignment or lock detector."""
MARKER=tuple((0xd3a679c54b1e82f0 >> k)&1 for k in range(64))

class Framer:
    def __init__(self,search_limit=2048):
        self.search_limit=search_limit
        self.reset()
    def reset(self):
        self.state='SEARCH';self.window=[];self.seen=0
        self.value=self.count=0
    def feed(self,bit):
        assert bit in (0,1)
        if self.state=='FAULT':return None
        if self.state=='SEARCH':
            self.seen+=1;self.window.append(int(bit))
            if len(self.window)>len(MARKER):self.window.pop(0)
            if tuple(self.window)==MARKER:
                self.state='PAYLOAD';self.window=[]
            elif self.seen>=self.search_limit:
                self.state='FAULT'
            return None
        self.value|=int(bit)<<self.count;self.count+=1
        if self.count==10:
            value=self.value;self.value=self.count=0
            return value
        return None

def controls():
    f=Framer()
    assert all(f.feed(0) is None for _ in range(2048))
    assert f.state=='FAULT'
    assert all(f.feed(b) is None for b in MARKER) and f.state=='FAULT'
    f.reset()
    assert all(f.feed(b) is None for b in MARKER) and f.state=='PAYLOAD'
    for b in (1,1,1):assert f.feed(b) is None
    f.reset()  # Partial payload must not survive retraining.
    for b in MARKER:assert f.feed(b) is None
    output=[f.feed((0x12a>>k)&1) for k in range(10)]
    assert output==[None]*9+[0x12a]
    damaged=list(MARKER);damaged[17]^=1
    f.reset()
    for b in damaged+[0]*2048:assert f.feed(b) is None
    assert f.state=='FAULT'
