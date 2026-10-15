"""Protected RF sample time descriptors on existing dense transport.

H2D opcode7 uses four metadata-only frames. D2H opcode8 uses six fragments
alongside ordinary IQ payload, retaining qc, so timestamps cannot stall samples.
The FPGA buffers samples while assembling their timestamp; chip storage is fixed.
"""
from stream_codec import metadata,unprotect,GUARD


def encode_time(epoch,counter,sequence,*,snapshot=False,iq_words=None):
    if type(epoch) is not int or not 0<=epoch<65536 or type(counter) is not int or not 0<=counter<1<<48:
        raise ValueError('Timestamp')
    if not snapshot and iq_words is not None:raise ValueError('No command payload')
    counts=[3,0,0,0,0,0] if iq_words is None else iq_words
    if snapshot and (len(counts)!=6 or counts[0]<3 or any(type(n) is not int or not 0<=n<=59 for n in counts)):
        raise ValueError('Snapshot IQ counts')
    value=counter|(epoch<<48)
    frames=[]
    for fragment in range(6 if snapshot else 4):
        width=11 if snapshot else 18
        part=(value>>(width*fragment))&((1<<width)-1)
        if snapshot:
            frames.append(metadata(part&63,counts[fragment],(sequence+fragment)%64,
                                   op=8,arg=(fragment<<5)|(part>>6)))
        else:
            frames.append(metadata(part&63,(part>>6)&63,(sequence+fragment)%64,
                                   op=7,arg=(fragment<<6)|(part>>12)))
    return frames


def decode_time(frames,sequence,*,snapshot=False,rf_owned=True):
    if not rf_owned or len(frames)!=(6 if snapshot else 4):raise ValueError('RF descriptor')
    value=0
    for i,header in enumerate(frames):
        if len(header)!=5 or header[4]!=GUARD or any(type(w) is not int or not 0<=w<1024 for w in header):
            raise ValueError('Header')
        word=unprotect(sum(w<<(10*j) for j,w in enumerate(header[:4])))
        arg=word>>22
        if (word>>12)&63!=(sequence+i)%64 or (word>>18)&15!=(8 if snapshot else 7):
            raise ValueError('Direction/sequence')
        if snapshot:
            if arg>>5!=i or (word>>6)&63>59 or (i==0 and (word>>6)&63<3):raise ValueError('Snapshot fragment/count')
            value|=((word&63)|((arg&31)<<6))<<(11*i)
        else:
            if arg>>6!=i:raise ValueError('Launch fragment')
            value|=((word&4095)|((arg&63)<<12))<<(18*i)
    if value>>64:raise ValueError('Nonzero reserved timestamp bits')
    return dict(epoch=value>>48,counter=value&((1<<48)-1))
