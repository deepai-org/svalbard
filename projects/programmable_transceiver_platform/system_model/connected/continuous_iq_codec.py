"""Unbounded-duration IQ packing with bounded residual state and no final padding.

Stopping requires the existing epoch/abort handshake; partial words are discarded.
No implicit end-of-stream marker is inferred from silence.
"""
class StreamEncoder:
    def __init__(self,bits):
        if bits not in (16,24):raise ValueError('Stream sample width')
        self.bits=bits;self.value=self.pending=0
    def push(self,sample):
        if not isinstance(sample,int) or not 0<=sample<1<<self.bits:raise ValueError('Sample width')
        self.value|=sample<<self.pending;self.pending+=self.bits;words=[]
        while self.pending>=10:
            words.append(self.value&1023);self.value>>=10;self.pending-=10
        return words

class StreamDecoder:
    def __init__(self,bits):
        StreamEncoder(bits);self.bits=bits;self.value=self.pending=0
    def feed(self,word):
        if not isinstance(word,int) or not 0<=word<1024:raise ValueError('Transport width')
        self.value|=word<<self.pending;self.pending+=10;samples=[]
        while self.pending>=self.bits:
            samples.append(self.value&((1<<self.bits)-1));self.value>>=self.bits;self.pending-=self.bits
        return samples
