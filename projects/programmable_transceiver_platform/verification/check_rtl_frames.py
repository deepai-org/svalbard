"""Decode RTL output with the independent existing Python frame codec."""
import json
import sys
from stream_codec import Receiver
from pathlib import Path
from frame_codec import decode
from transport_model import schedule

v2="--v2" in sys.argv
results=[]
for mode in (0,1):
    path=Path(f'/out/core_v2_{mode}_words.txt' if v2 else f'/out/core{mode}_words.txt')
    words=[int(x,16) for x in path.read_text().split()]
    # Trace stops at first injected corruption; only clean operation is cross-checked.
    prefix=[0x3a5,0x05a,0x2d3,0x12c]+([0x369,0x096,0x21e,0x1e1] if v2 else [])
    assert words[:len(prefix)]==prefix,'training'
    words=words[len(prefix):]
    slots=schedule({'wire':52,'iq':7} if mode else {'wire':33,'iq':25})
    wire=[];bits=[];frames=len(words)//64
    rx=Receiver(mode)
    for index in range(frames):
        frame_words=words[index*64:(index+1)*64]
        if v2:
            events=[rx.feed(w) for w in frame_words]
            wire.extend(e[1] for e in events if e and e[0]=='wire')
            iq=[e[1] for e in events if e and e[0]=='iq']
        else:
            frame=decode(slots,frame_words,index%64)
            wire.extend(frame.wire);iq=frame.iq
        bits.extend((word>>bit)&1 for word in iq for bit in range(10))
    expected=0
    for word in wire:
        assert word==expected,'RTL wired payload differs from generated source'
        expected=((expected+37)&1023)^0x15
    width=16 if mode else 24
    samples=len(bits)//width
    for index in range(samples):
        value=sum(b<<i for i,b in enumerate(bits[index*width:(index+1)*width]))
        i=(index*7)%4096 if index else 0
        q=(index*13+1024)%4096 if index else 0
        expected=((q>>4)<<8)|(i>>4) if mode else (q<<12)|i
        assert value==expected, f'RTL IQ bit packing mismatch mode={mode} index={index}'
    assert frames>200 and len(wire)>1000 and samples>500
    results.append({'mode':mode,'decoded_frames':frames,'wire_words':len(wire),'iq_samples':samples})
Path('/out/rtl-frame-crosscheck-v2.json' if v2 else '/out/rtl-frame-crosscheck.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results))
