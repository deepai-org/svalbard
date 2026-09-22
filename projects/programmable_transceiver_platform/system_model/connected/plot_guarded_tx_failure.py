"""Visual diagnostic of the saved TX failure; original held-out gain retained."""
import json
import numpy as np
from html import escape
import subprocess
from chip_model import P

def main():
    data=np.load(P/'evidence/connected-guarded-limited-pad-quality-mode1-traces.npz')
    t=data['time_s'];x=data['ideal_pad'];y=data['actual_pad'];split=len(x)//4
    gain=np.vdot(x[:split],y[:split])/np.vdot(x[:split],x[:split]);a=gain*x
    us=(t-t[0])*1e6
    # Phase at envelope nulls is undefined/unstable; mask it in the visual only.
    mask=(abs(a)>max(abs(a))*.05)&(abs(y)>max(abs(y))*.05)
    phase=np.full(len(x),np.nan);phase[mask]=np.angle(y[mask]*np.conj(a[mask]))*180/np.pi
    out=P/'evidence';parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="880" viewBox="0 0 1200 880"><rect width="1200" height="880" fill="white"/><g font-family="sans-serif" font-size="16">']
    def text(x,y,label,size=16):parts.append(f'<text x="{x}" y="{y}" font-size="{size}">{escape(label)}</text>')
    text(40,35,'Mode 1 TX failure: 14.85% held-out error; original training gain',23)
    text(40,65,'Gray: training quarter. Phase masked near envelope nulls for display only; quality uses all samples.')
    panels=[('Envelope (V RMS)',[(abs(a),'#2364aa'),(abs(y),'#df7618')]),
            ('Phase residual (degrees)',[(phase,'#2364aa')]),
            ('Complex error (V RMS)',[(abs(y-a),'#c63333')])]
    for j,(title,series) in enumerate(panels):
        top=115+j*240;bottom=top+175;left=110;right=1150
        finite=np.concatenate([v[np.isfinite(v)] for v,_ in series]);lo=min(0.,float(min(finite)));hi=float(max(finite));span=max(hi-lo,1e-12)
        def xp(v):return left+(v-us[0])/(us[-1]-us[0])*(right-left)
        def yp(v):return bottom-(v-lo)/span*(bottom-top)
        text(40,top-15,title)
        parts.append(f'<rect x="{left}" y="{top}" width="{xp(us[split])-left}" height="175" fill="#eee"/>')
        for val in np.linspace(lo,hi,5):
            py=yp(val);parts.append(f'<path d="M{left},{py} H{right}" stroke="#ddd"/>');text(10,py+5,f'{val:.3g}',13)
        for val in np.linspace(us[0],us[-1],7):
            px=xp(val);parts.append(f'<path d="M{px},{top} V{bottom}" stroke="#ddd"/>');text(px-12,bottom+22,f'{val:.2f}',13)
        for values,color in series:
            segments=[];pen=False
            for tx,v in zip(us,values):
                if not np.isfinite(v):pen=False;continue
                segments.append(f'{"L" if pen else "M"}{xp(tx):.3f},{yp(v):.3f}');pen=True
            parts.append(f'<path d="{" ".join(segments)}" fill="none" stroke="{color}" stroke-width="1.2"/>')
    text(500,850,'Time since first observed host word (µs)')
    text(700,96,'Blue: ideal × gain; orange: actual envelope',14)
    parts.append('</g></svg>');path=out/'guarded-mode1-tx-failure.svg';path.write_text('\n'.join(parts))
    subprocess.run(['rsvg-convert',str(path),'-o',str(out/'guarded-mode1-tx-failure.png')],check=True)
    print('Rendered guarded-mode1-tx-failure.svg and .png')
if __name__=='__main__':main()
