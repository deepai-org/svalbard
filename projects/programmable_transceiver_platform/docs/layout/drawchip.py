import json, sys, re, math
from PIL import Image, ImageDraw, ImageFont

chip, src, out, stamp = sys.argv[1:5]
place = json.load(open(f'{src}/place.json'))['blocks']
pads = json.load(open(f'{src}/pads.json'))
padd = dict(pads['pads']) if isinstance(pads['pads'], list) else pads['pads']
io = dict(pads['io']) if isinstance(pads['io'], list) else pads['io']

S = 0.32; W, H = 3932, 5122; M = 30; LEG = 330
img = Image.new('RGB', (int(W*S) + 2*M + LEG, int(H*S) + 2*M + 40), 'white')
d = ImageDraw.Draw(img)
def font(sz):
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        try: return ImageFont.truetype(f, sz)
        except OSError: pass
    return ImageFont.load_default()
F7, F9, F11, F14 = font(9), font(11), font(13), font(16)
def X(x): return M + x*S
def Y(y): return M + 40 + (H - y)*S
def rect(bb, fill, outline='black', w=1): d.rectangle([X(bb[0]), Y(bb[3]), X(bb[2]), Y(bb[1])], fill=fill, outline=outline, width=w)

CATS = [
    (r'^digital$', 'digital macro', (217, 217, 217)),
    (r'^(lna|rxmix|bbfilter|bb_tap_[iq]$)', 'RF receive', (78, 121, 167)),
    (r'^(dac_|txmix|txsum|rfdriver)', 'RF transmit', (225, 87, 89)),
    (r'^(qvco|lo_|vco_replica$)', 'LO synthesiser', (242, 142, 43)),
    (r'^(adc_|refbuf)', 'converters', (118, 183, 178)),
    (r'^(ctle|slicer|wrx_cap|detect|termination|term_buffer|vthdac|wordclk|rxselect)', 'wired receive', (89, 161, 79)),
    (r'^(wiredtx|usb_txdrv|attached|rx_wtx_ext|txpad_bias)', 'wired transmit', (176, 122, 161)),
    (r'^(pll_|cdr|clockmux|clk_obs|rx_ref|rx_aux|ptrim|prescale|obs_pre|pd_clk)', 'clocks / rings', (237, 201, 72)),
    (r'^(core_bias|isw|iso|decap|refvcm|por|aosc|bringup)', 'bias / power / decap', (186, 176, 172)),
    (r'^(char|atb|bb_tap_wmon)', 'test / characterisation', (255, 157, 167)),
]
def cat(n):
    for rx, name, col in CATS:
        if re.search(rx, n): return name, col
    return 'other', (238, 238, 238)

PATHS = {
 'rf': [('pad_rf_rx', 'lna', 'RF in'), ('lna', 'rxmix_i', ''), ('lna', 'rxmix_q', ''), ('rxmix_i', 'bbfilter_i', ''),
  ('rxmix_q', 'bbfilter_q', ''), ('bbfilter_i', 'adc_i', ''), ('bbfilter_q', 'adc_q', ''), ('adc_i', 'digital', 'I/Q'),
  ('adc_q', 'digital', ''), ('digital', 'dac_i', ''), ('digital', 'dac_q', ''), ('dac_i', 'txmix_i', ''), ('dac_q', 'txmix_q', ''),
  ('txmix_i', 'rfdriver', ''), ('txmix_q', 'rfdriver', ''), ('rfdriver', 'pad_rf_tx', 'RF out'),
  ('lo_vreg', 'qvco', 'LO supply'), ('qvco', 'lo_mmd', 'feedback'), ('lo_mmd', 'lo_pfdcp', ''), ('lo_pfdcp', 'lo_lf', ''),
  ('lo_lf', 'qvco', 'VTUNE'), ('qvco', 'lo_ext', 'LO'), ('lo_ext', 'rxmix_i', ''), ('lo_ext', 'txmix_i', ''),
  ('pad_ref', 'rx_ref_in', 'REF'), ('rx_ref_in', 'pll_tx', ''), ('pll_tx', 'clockmux', ''), ('clockmux', 'digital', 'clocks')],
 'wired': [('pad_hs_rx', 'ctle', 'line in'), ('ctle', 'slicer', ''), ('slicer', 'wrx_cap', ''), ('wrx_cap', 'digital', 'words'),
  ('pad_hs_rx', 'detect', ''), ('pll_cdr', 'ptrim', 'RX phases'), ('ptrim', 'slicer', ''), ('wrx_cap', 'cdr', 'votes'),
  ('cdr', 'pll_cdr', ''), ('digital', 'wiredtx', 'TX data'), ('pll_tx', 'wiredtx', 'TX phases'), ('wiredtx', 'pad_wire_tx', 'line out'),
  ('digital', 'usb_txdrv', 'USB'), ('usb_txdrv', 'pad_usb', ''), ('pad_ref', 'rx_ref_in', 'REF'), ('rx_ref_in', 'pll_tx', ''),
  ('pll_tx', 'clockmux', ''), ('clockmux', 'digital', 'clocks'), ('pad_wtx_ext', 'rx_wtx_ext', 'ext data')],
}
def centre(n):
    bb = place[n]['bbox'] if n in place else padd[n]['bbox'] if n in padd else None
    return None if bb is None else ((bb[0]+bb[2])/2, (bb[1]+bb[3])/2)

d.text((M, 8), f'pt_{chip}: placed blocks from the assembly run of {stamp}; main signal paths in red', fill='black', font=F14)
rect([0, 0, W, H], None, 'black', 2)
for v in io.values(): rect(v['bbox'], (240, 240, 240), (160, 160, 160))
for n, v in padd.items():
    bb = v['bbox']; rect(bb, (85, 85, 85))
    d.text(((X(bb[0])+X(bb[2]))/2, (Y(bb[1])+Y(bb[3]))/2), n.replace('pad_', ''), fill='white', font=F9, anchor='mm')
seen = {}
for n, v in place.items():
    bb = v['bbox']; name, col = cat(n); seen[name] = col
    rect(bb, col, (40, 40, 40))
    if v.get('kind') in ('placeholder', 'demand'):
        for k in range(int(X(bb[0])), int(X(bb[2])), 6): d.line([(k, Y(bb[3])), (min(k+20, X(bb[2])), Y(bb[1]))], fill='black')
for n, v in place.items():
    bb = v['bbox']; a = (bb[2]-bb[0])*(bb[3]-bb[1])
    if a > 9000 and not n.startswith('decap'):
        d.text(((X(bb[0])+X(bb[2]))/2, (Y(bb[1])+Y(bb[3]))/2), n, fill='black', font=F11 if a > 60000 else F7, anchor='mm')
RED = (200, 0, 0)
for a, b, lab in PATHS[chip]:
    pa, pb = centre(a), centre(b)
    if not pa or not pb: continue
    x0, y0, x1, y1 = X(pa[0]), Y(pa[1]), X(pb[0]), Y(pb[1])
    d.line([(x0, y0), (x1, y1)], fill=RED, width=3)
    ang = math.atan2(y1-y0, x1-x0)
    for s in (+0.45, -0.45):
        d.line([(x1, y1), (x1 - 14*math.cos(ang+s), y1 - 14*math.sin(ang+s))], fill=RED, width=3)
    if lab: d.text(((x0+x1)/2 + 4, (y0+y1)/2 - 12), lab, fill=RED, font=F11)
lx, ly = int(W*S) + 2*M + 10, M + 50
d.text((lx, ly), 'Legend', fill='black', font=F14); ly += 26
for name, col in seen.items():
    d.rectangle([lx, ly, lx+18, ly+14], fill=col, outline='black'); d.text((lx+26, ly), name, fill='black', font=F11); ly += 22
d.rectangle([lx, ly, lx+18, ly+14], fill=(85, 85, 85)); d.text((lx+26, ly), 'custom pads', fill='black', font=F11); ly += 22
d.rectangle([lx, ly, lx+18, ly+14], fill=(240, 240, 240), outline=(160, 160, 160)); d.text((lx+26, ly), 'foundry pad ring cells', fill='black', font=F11); ly += 22
d.line([(lx, ly+7), (lx+18, ly+7)], fill=RED, width=3); d.text((lx+26, ly), 'main signal path', fill='black', font=F11); ly += 30
d.text((lx, ly), f'die 3.932 x 5.122 mm\nscale {S*1000:.0f} px/mm', fill='black', font=F11)
img.save(out); print('wrote', out, img.size)
