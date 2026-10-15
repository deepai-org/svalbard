"""Protected generic gain command/status metadata for exclusive RF transport.

Opcode4 is atomic LNA/PGA gain; no packet parsing or protocol profile. Existing
legacy Receiver RTL rejects it until integrated; this reference is normative.
"""
from stream_codec import metadata,unprotect,GUARD
LNA=(-6,0,10,20)
PGA=tuple(range(-6,43,3))
MAX_INVALID_PAIRS=127
MAX_STALE_PAIRS=24


def encode_gain(lna_db,pga_db,sequence,*,invalid_pairs=0,iq_words=0,status=False):
    if lna_db not in LNA or pga_db not in PGA:raise ValueError('gain range')
    if not status and (invalid_pairs or iq_words):raise ValueError('command has no data/gap')
    if not 0<=invalid_pairs<=MAX_INVALID_PAIRS or not 0<=iq_words<=59:raise ValueError('frame count')
    arg=(LNA.index(lna_db)<<5)|PGA.index(pga_db)
    return metadata(invalid_pairs&63,iq_words,sequence,op=4,arg=arg|((invalid_pairs>>6)<<7))


def decode_gain(header,sequence,*,status=False,rf_owned=True):
    if not rf_owned or len(header)!=5 or header[4]!=GUARD:raise ValueError('RF header/ownership')
    if any(type(w) is not int or not 0<=w<1024 for w in header):raise ValueError('word')
    value=unprotect(sum(w<<(10*i) for i,w in enumerate(header[:4])))
    invalid=value&63;iq=(value>>6)&63;seq=(value>>12)&63;op=(value>>18)&15;arg=value>>22
    if seq!=sequence or op!=4 or (not status and arg&128) or (arg&31)>=len(PGA) or iq>59:
        raise ValueError('gain metadata')
    if not status and (invalid or iq):raise ValueError('command payload')
    return dict(lna_db=LNA[(arg>>5)&3],pga_db=PGA[arg&31],invalid_pairs=invalid|((arg>>7)<<6),iq_words=iq)


def encode_epoch(epoch,sequence,phase):
    if type(epoch) is not int or not 0<=epoch<65536 or phase not in ('arm','ready','ack'):
        raise ValueError('epoch/phase')
    flags={'arm':3,'ready':1,'ack':2}
    return metadata(epoch&63,(epoch>>6)&63,sequence,op=6,arg=(flags[phase]<<4)|(epoch>>12))


def decode_epoch(header,sequence,phase):
    if len(header)!=5 or header[4]!=GUARD or any(type(w) is not int or not 0<=w<1024 for w in header):raise ValueError('epoch header')
    value=unprotect(sum(w<<(10*i) for i,w in enumerate(header[:4])))
    arg=value>>22
    flags={'arm':3,'ready':1,'ack':2}
    if phase not in flags or (value>>18)&15!=6 or (value>>12)&63!=sequence or arg>>4!=flags[phase]:
        raise ValueError('epoch sequence/phase')
    return (value&63)|(((value>>6)&63)<<6)|((arg&15)<<12)


class GainSampleReceiver:
    """FPGA-side RF words to timestamped pairs across protected gain gaps.

    A validated six-fragment snapshot establishes absolute pair indices. The
    first five fragments' samples remain buffered on the FPGA until validation.
    A partial old pair is included in wc; it is never added to the gap twice.
    """
    def __init__(self,first_sample=0,*,first_sequence=0):
        from stream_codec import Receiver
        if type(first_sample) is not int or first_sample<0:raise ValueError('Sample origin')
        if type(first_sequence) is not int or not 0<=first_sequence<64:raise ValueError('Frame sequence')
        self.receiver=Receiver(1,owner='iq',rf_gain_status=True)
        self.receiver.sequence=first_sequence
        self.next_sample=first_sample;self.bits=0;self.buffer=0;self.fault=False
        self.snapshot_headers=[];self.snapshot_samples=[];self.snapshot_start=None

    def feed(self,word):
        if self.fault:raise ValueError('Sample receiver requires reset/snapshot')
        try:
            event=self.receiver.feed(word)
            if event is None:return None
            kind,value=event
            if kind=='command' and self.snapshot_headers:
                raise ValueError('Snapshot interrupted by ordinary metadata')
            if kind=='snapshot':
                from rf_timing_command import decode_time
                from stream_codec import unprotect
                decoded=unprotect(sum(value[i]<<(10*i) for i in range(4)))
                fragment=(decoded>>22)>>5
                if fragment==0:
                    if self.snapshot_headers:raise ValueError('Interrupted snapshot')
                    self.snapshot_start=self.next_sample
                    self.buffer=0;self.bits=0
                if fragment!=len(self.snapshot_headers):raise ValueError('Snapshot fragment order')
                self.snapshot_headers.append(value)
                if len(self.snapshot_headers)<6:return None
                first=unprotect(sum(self.snapshot_headers[0][i]<<(10*i) for i in range(4)))
                stamp=decode_time(self.snapshot_headers,(first>>12)&63,snapshot=True)
                shift=stamp['counter']-self.snapshot_start
                self.next_sample+=shift
                for sample in self.snapshot_samples:sample['sample_index']+=shift
                result=dict(kind='snapshot',**stamp,samples=self.snapshot_samples)
                self.snapshot_headers=[];self.snapshot_samples=[];self.snapshot_start=None
                return result
            if kind=='gain':
                if self.snapshot_headers:raise ValueError('Gain status interrupted snapshot')
                gap=value['invalid_pairs']
                if self.bits and gap==0:raise ValueError('Partial old pair must be counted in gain gap')
                result=dict(kind='gap',first_sample=self.next_sample,count=gap,
                            lna_db=value['lna_db'],pga_db=value['pga_db'])
                self.buffer=0;self.bits=0;self.next_sample+=gap
                return result
            if kind=='iq':
                self.buffer|=value<<self.bits;self.bits+=10
                if self.bits>=24:
                    result=dict(kind='sample',sample_index=self.next_sample,value=self.buffer&0xffffff)
                    self.buffer>>=24;self.bits-=24;self.next_sample+=1
                    if self.snapshot_headers:
                        if len(self.snapshot_samples)>=256:raise ValueError('FPGA snapshot buffer full')
                        self.snapshot_samples.append(result);return None
                    return result
            return None
        except ValueError:
            self.fault=True
            raise
