"""Candidate finite-burst contract: declared sample count, zero final-word padding.

Length is a coherent management descriptor agreed before payload, not inferred
from silence or frame quotas. Descriptor transport/CDC is not implemented here.
"""

class BurstEncoder:
    def __init__(self, bits, count):
        if bits not in (16,24) or not isinstance(count,int) or count<0:
            raise ValueError('burst descriptor')
        self.bits=bits;self.count=count;self.accepted=0
        self.value=self.pending=0;self.closed=False
    def push(self, sample):
        if self.closed or self.accepted>=self.count:
            raise ValueError('burst overrun')
        if not isinstance(sample,int) or not 0<=sample<1<<self.bits:
            raise ValueError('sample width')
        self.value|=sample<<self.pending;self.pending+=self.bits
        self.accepted+=1;words=[]
        while self.pending>=10:
            words.append(self.value&1023);self.value>>=10;self.pending-=10
        return words
    def finish(self):
        if self.closed or self.accepted!=self.count:
            raise ValueError('incomplete or closed burst')
        words=[self.value] if self.pending else []
        self.value=self.pending=0;self.closed=True
        return words


class BurstDecoder:
    def __init__(self,bits,count):
        BurstEncoder(bits,count)  # Same descriptor validation.
        self.bits=bits;self.count=count;self.expected_words=(bits*count+9)//10
        self.words=self.delivered=self.value=self.pending=0;self.closed=False;self.fault=False
    def fail(self,reason):
        self.fault=True
        raise ValueError(reason)
    def feed(self,word):
        if self.fault:raise ValueError('Faulted burst requires a new descriptor/epoch')
        if self.closed or self.words>=self.expected_words:
            self.fail('extra burst word')
        if not isinstance(word,int) or not 0<=word<1024:
            self.fail('transport word width')
        # Validate final padding before releasing any samples from this word.
        valid=self.bits*self.count-10*self.words
        if valid<10 and word>>valid:
            self.fail('nonzero final padding')
        self.value|=word<<self.pending;self.pending+=min(valid,10);self.words+=1
        samples=[]
        while self.pending>=self.bits:
            samples.append(self.value&((1<<self.bits)-1))
            self.value>>=self.bits;self.pending-=self.bits;self.delivered+=1
        return samples
    def finish(self):
        if self.fault:raise ValueError('Faulted burst cannot finish')
        if self.closed or self.words!=self.expected_words or self.delivered!=self.count or self.pending or self.value:
            self.fail('incomplete or closed burst')
        self.closed=True


def controls():
    def reject(fn):
        try:fn()
        except ValueError:return
        raise AssertionError('Invalid burst accepted')
    # Independent bit-order vector: one16-bit sample uses two10-bit words.
    encoder=BurstEncoder(16,1)
    assert encoder.push(0xabcd)==[0x3cd]
    assert encoder.finish()==[0x2a]
    decoder=BurstDecoder(16,1)
    assert decoder.feed(0x3cd)==[]
    reject(lambda:decoder.feed(0x6a))  # Bit6 is padding, not a sample bit.
    assert decoder.fault and decoder.delivered==0
    snapshot=(decoder.words,decoder.value,decoder.pending)
    reject(lambda:decoder.feed(0x2a))  # Retry must not revive this epoch.
    reject(decoder.finish)
    assert snapshot==(decoder.words,decoder.value,decoder.pending)
    decoder=BurstDecoder(16,1)  # Explicit new descriptor/epoch.
    assert decoder.feed(0x3cd)==[]
    assert decoder.feed(0x2a)==[0xabcd]
    decoder.finish();reject(lambda:decoder.feed(0))
    reject(lambda:BurstEncoder(24,1).finish())
    short=BurstDecoder(24,1)
    reject(short.finish);assert short.fault
    reject(lambda:short.feed(0))
    # Streaming delivery cannot retract a sample emitted before a later fault.
    partial=BurstDecoder(16,2)
    assert partial.feed(0)==[] and partial.feed(0)==[0]
    assert partial.feed(0)==[]
    reject(lambda:partial.feed(4))  # Only two payload bits remain.
    assert partial.fault and partial.delivered==1
    reject(lambda:partial.feed(0))
    encoder=BurstEncoder(24,0);assert encoder.finish()==[]
    decoder=BurstDecoder(24,0);decoder.finish()
    reject(lambda:encoder.push(0))


if __name__=='__main__':
    import hashlib,json,sys
    from pathlib import Path
    P=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(P/'verification'))
    from stream_codec import encode,Receiver,slots
    controls();cases=[]
    for mode,bits in ((0,24),(1,16)):
        for count in range(130):
            source=[((i*7919)^0xabcdef)&((1<<bits)-1) for i in range(count)]
            encoder=BurstEncoder(bits,count);words=[]
            for sample in source:words.extend(encoder.push(sample))
            words.extend(encoder.finish())
            decoder=BurstDecoder(bits,count);rx=Receiver(mode);recovered=[];wire=[]
            quota=slots(mode).count('iq');frames=max(1,(len(words)+quota-1)//quota)
            for frame in range(frames):
                for word in encode(mode,[frame&1023],words[frame*quota:(frame+1)*quota],frame%64):
                    event=rx.feed(word)
                    if event and event[0]=='iq':recovered.extend(decoder.feed(event[1]))
                    elif event and event[0]=='wire':wire.append(event[1])
            decoder.finish()
            assert recovered==source and wire==[i&1023 for i in range(frames)]
            cases.append(dict(mode=mode,samples=count,transport_words=len(words),padding_bits=(-bits*count)%10))
    report=dict(status='passed',cases=cases,complete_architecture=False,
        source_hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in
          (Path(__file__),P/'verification/stream_codec.py',P/'verification/transport_model.py')},
        limitations=['Declared count is an abstract coherent management contract; descriptor transport and CDC remain unspecified.',
          'Timed single-burst return is integrated separately; back-to-back epochs and reset propagation remain open.',
          'Decoder faults latch until a new descriptor/epoch; previously streamed samples cannot be retracted.',
          'Padding validation is not payload integrity or authentication; incorrect descriptors can still misinterpret valid data.'])
    (P/'evidence/connected-burst-codec.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(cases)} framed finite bursts pass; malformed padding and incomplete bursts rejected')
