"""Digitize the published FFT inset from its native embedded raster.
Usage: python figure7_screen.py PAPER.pdf
Requires pdftocairo, Pillow, numpy, scipy. Pixel coordinates are specific to the
898x822 embedded Figure7 image in NIST pub957346; never use for a different plot.
"""
import base64,hashlib,json,subprocess,sys,tempfile,itertools
from pathlib import Path
from xml.etree import ElementTree as ET
import numpy as np
from PIL import Image
from scipy.signal import find_peaks
from scipy.optimize import brentq
from numpy.polynomial import chebyshev as cheb
paper=Path(sys.argv[1])
with tempfile.TemporaryDirectory(prefix='afe-figure7-') as td:
 svg=Path(td)/'page.svg'
 subprocess.run(['pdftocairo','-f','6','-l','6','-svg',str(paper),str(svg)],check=True,capture_output=True)
 elements=[e for e in ET.parse(svg).getroot().iter() if e.tag.endswith('image')]
 assert len(elements)==1 and elements[0].get('width')=='898' and elements[0].get('height')=='822'
 blob=base64.b64decode(elements[0].get('{http://www.w3.org/1999/xlink}href').split(',')[1])
 raster=Path(td)/'figure.png';raster.write_bytes(blob)
 pixels=np.array(Image.open(raster).convert('RGB')).astype(int)
 region=pixels[20:349,452:800]
 # Dark blue trace, excluding black arrows and axes. Native pixels, no upscale.
 mask=(region[:,:,2]-region[:,:,0]>50)&(region[:,:,1]-region[:,:,0]>20)&(region[:,:,2]-region[:,:,1]>20)
 envelope=np.where(mask,np.arange(20,349)[:,None],350).min(axis=0)
 locations,properties=find_peaks(-envelope.astype(float),prominence=12,distance=8)
 # Visually checked native inset ordinate ticks:0,-25,-50,-75,-100dBFS.
 levels=np.array([0,-25,-50,-75,-100]);tick_y=np.array([32,112,192,271,351])
 slope,offset=np.polyfit(tick_y,levels,1)
 peaks=[dict(x_pixel=int(x+452),y_pixel=int(envelope[x]),plot_dbfs=float(slope*envelope[x]+offset)) for x in locations]
 strongest=sorted(peaks,key=lambda r:r['plot_dbfs'],reverse=True)
 fundamental=strongest[0];assert fundamental['x_pixel']==767
 for peak in peaks:peak['relative_to_fundamental_db']=peak['plot_dbfs']-fundamental['plot_dbfs']
 spurs=sorted(strongest[1:4],key=lambda r:r['x_pixel'],reverse=True)
 spacings=np.diff([p['x_pixel'] for p in spurs[::-1]]+[fundamental['x_pixel']]).tolist()
 # Conditional shape comparison: assign the three peaks to aliased3/5/7.
 # Memoryless transfer harmonic ratios are independent of the chosen test tone
 # until sampling aliases them; use a dense coherent cosine to avoid bin leakage.
 target_db=np.array([p['relative_to_fundamental_db'] for p in spurs])
 target=10**(target_db/20)
 x=np.cos(2*np.pi*np.arange(32768)/32768)
 def ratios(y):
  spectrum=abs(np.fft.rfft(y))
  return spectrum[[3,5,7]]/spectrum[1]
 model_rows=[]
 for name,transfer,bounds in [
   ('symmetric_hard_clip',lambda a:np.clip(x,-a,a),(.1,.99999)),
   ('tanh_compression',lambda a:np.tanh(a*x),(.01,10)),
   ('arctangent_compression',lambda a:np.arctan(a*x),(.01,10))]:
  parameter=brentq(lambda a:ratios(transfer(a))[0]-target[0],*bounds)
  db=20*np.log10(ratios(transfer(parameter)))
  model_rows.append(dict(model=name,parameter=float(parameter),harmonics_dbc=db.tolist(),errors_vs_figure_db=(db-target_db).tolist()))
 # Construct distinct monotone transfers with the same three magnitudes.
 # This proves a non-unique inverse even under the assumed harmonic identities.
 ambiguities=[]
 for signs in itertools.product([-1,1],repeat=3):
  coefficients=np.zeros(8);coefficients[1]=1
  coefficients[[3,5,7]]=target*np.array(signs)
  derivative=cheb.chebder(coefficients)
  roots=cheb.chebroots(cheb.chebder(derivative))
  points=[-1,1]+[r.real for r in roots if abs(r.imag)<1e-10 and -1<r.real<1]
  minimum=float(min(cheb.chebval(points,derivative)))
  assert minimum>0
  y=cheb.chebval(x,coefficients)
  error=float(max(abs(20*np.log10(ratios(y))-target_db)))
  assert error<1e-9
  ambiguities.append(dict(harmonic_signs=list(signs),minimum_transfer_slope=minimum,maximum_harmonic_fit_error_db=error))
 shape_comparison=dict(assumption='Inset peaks assigned to3rd/5th/7th harmonics. Conditional shape test, not proof of those identities or a silicon transfer fit.',
   target_harmonics_dbc=target_db.tolist(),third_harmonic_matched_models=model_rows,
   nonunique_monotone_transfers=ambiguities,
   construction='y=x+sum(sign[n]*amplitude[n]*T_n(x)), n=3,5,7, x in[-1,1]. Fundamental normalized to1; harmonic phases unobserved.',
   conclusion='These simple clipping/compression families fail to jointly reproduce the peaks. Eight distinct monotone polynomial transfers reproduce their magnitudes exactly, so magnitudes alone do not identify transfer curvature or physical cause.')
 print(json.dumps(dict(conditional_shape_comparison=shape_comparison,paper_url='https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957346',paper_sha256=hashlib.sha256(paper.read_bytes()).hexdigest(),embedded_raster_sha256=hashlib.sha256(blob).hexdigest(),
   analysis_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),native_raster_size=[898,822],inset_crop_xy=[452,20,800,349],ordinate_calibration=dict(pixel_y=tick_y.tolist(),dbfs=levels.tolist()),
   detected_peaks=peaks,fundamental=fundamental,strongest_three_nonfundamental_inset_peaks=spurs,
   strong_peak_pixel_spacings=spacings,practical_reading_precision_db='About1dB; approximate raster reading, not statistical confidence interval.',
   conditional_harmonic_interpretation=dict(assumed_sample_rate_msps=10,annotated_input_mhz=4.99023,odd_orders=[3,5,7],aliased_frequencies_mhz=[abs(((h*4.99023+5)%10)-5) for h in [3,5,7]],
      interpretation='Approximately equally spaced peaks are compatible with folded odd harmonics nearNyquist; modulation/other mechanisms can also produce a comb. No unique circuit cause inferred.'),
   limitations=['Inset-only largest spur separation is not full-band SFDR; obscured/outside spurs are not bounded.',
     'dBFS labeling alone does not establish absolute input voltage or FFT normalization. Peak pixel locations do not recover raw samples, bin power or integrated noise.',
     'The table20MS/s conditions are not established for this near5MHz Nyquist figure; do not combine their metrics as a single trace.',
     'Several visible distortion peaks constrain spectral shape beyond one harmonic, but do not identify capacitor mismatch, reference error or sampling nonlinearity uniquely.']),indent=2))
