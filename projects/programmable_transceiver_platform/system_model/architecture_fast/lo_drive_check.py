"""Independent analytic limits for loaded-LO dropout sensitivity."""
import hashlib,json,math
from pathlib import Path
from lo_drive import coefficient,iq_projection,square_fixture
P=Path(__file__).resolve().parents[2]

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    rows=[];carrier=2.4e9
    for period in (None,16,8,4):
        edges,iv,qv=square_fixture(carrier,240,period)
        p=iq_projection(edges,iv,qv,carrier)
        drop=0 if period is None else 1/period
        assert abs(p['desired']-(1-drop/2))<1e-12
        assert abs(p['image']+drop/2)<1e-12
        expected=drop/(2-drop)
        assert abs(p['image_relative_rms']-expected)<1e-12
        # Splitting every interval must not alter the measured coefficients.
        split=[edges[0]];values=[]
        for a,b,v in zip(edges,edges[1:],iv):split.extend(((a+b)/2,b));values.extend((v,v))
        assert abs(coefficient(split,values,carrier)-coefficient(edges,iv,carrier))<1e-12
        sideband=0 if period is None else abs(coefficient(edges,iv,carrier+carrier/period))
        rows.append(dict(missing_i_period_cycles=period,i_missing_fraction=drop,
            desired_gain=abs(p['desired']),image_gain=abs(p['image']),
            image_relative_rms=p['image_relative_rms'],upper_sideband_coefficient=sideband,
            image_only_below_10_percent=p['image_relative_rms']<=.1))
    assert rows[2]['image_only_below_10_percent'] and not rows[3]['image_only_below_10_percent']
    files=[Path(__file__),Path(__file__).with_name('lo_drive.py')]
    report=dict(status='passed',source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},cases=rows,
        physical_qualification=False,limitations=['Normalized switching effectiveness, not transistor gate voltage or threshold crossings.',
        'Image-only RMS assumes equal-power uncorrelated complex signal and its conjugate after one complex-gain correction.',
        'Additional dropout sidebands, DC, loading, noise and receiver filtering are not included in this RMS bound.',
        'Sensitivity model is not yet connected to full-chip mixing or actual transistor waveforms.'])
    (P/'evidence/fast-lo-drive.json').write_text(json.dumps(report,indent=2)+'\n');print(rows)
if __name__=='__main__':main()
