#!/usr/bin/env python3
"""netres spec for pad_hspad (stacked build, published or fixed).  spec_hspad.py > res/spec_hspad.json
Leg P occupies y 440.8-594.75, leg N (mirrored) 636.75-790.7; mirror: y_N = 1231.5 - y_P.  Bond openings (37/0): P (7.5,2)-(67.5,62), N (218.5,2)-(278.5,62)."""
import json, sys
# optional argument: the build's config.json (leg height / PAD trunk start differ between the published and the fixed leg)
cfg = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else dict(leg_top=154.75, pad_trunk_lo=51.97)
YP = 594.75 - cfg['leg_top']; YN = 636.75 + cfg['leg_top']            # leg origins (P unmirrored, N mirrored in y)
dy = (YP - 440.) + (cfg['pad_trunk_lo'] - 51.97)                         # shift of the MIM row against the published cell
LEGP = [319, 430, 492, 596]; LEGN = [319, 635.5, 492, 801]; MID = 615.75
mir = lambda b: [b[0], 1231.5 - b[3], b[2], 1231.5 - b[1]]
mimbot = [[340, 495.77 + dy, 377.4, 531.97 + dy], [379.4, 495.77 + dy, 416.8, 531.97 + dy]]      # Metal4 bottom plates (PAD)
mimtop = [[341, 496.77 + dy, 375.2, 530.97 + dy], [380.4, 496.77 + dy, 414.6, 530.97 + dy]]      # Metal5 over the MIM top plates (RX)
ypn = YN - (cfg['pad_trunk_lo'] + 1.5)
nets = []
nets.append(dict(name='TERM_VCM', max_step=0.25, min_width=2.0, min_cuts=4, terminals=[
    dict(name='pin', layer='M5', box=[491, 627.25, 492, 628.25]),
    dict(auto_contacts='src')],
    groups=dict(srcP=dict(prefix='src', window=LEGP), srcN=dict(prefix='src', window=LEGN),
                srcP_1k=dict(prefix='src', window=LEGP, ballast_ohm=1000.), srcN_1k=dict(prefix='src', window=LEGN, ballast_ohm=1000.)),
    pairs=[['srcP', 'srcN'], ['srcP_1k', 'srcN_1k'], ['pin', 'srcP'], ['pin', 'srcN'], ['pin', 'srcP_1k'], ['pin', 'srcN_1k']]))
# `feed`: Metal5 where the composer strap leaves the shell PAD trunk (P: x 294, y 414-418; N: x 310, y 736.03-740.03)
for s, leg, bond, mb, feed in (('P', LEGP, [7.5, 2, 67.5, 62], mimbot, [294, 414, 294.5, 418]), ('N', LEGN, [218.5, 2, 278.5, 62], [mir(b) for b in mimbot], [310, ypn - 2, 310.5, ypn + 2])):
    nets.append(dict(name=f'PAD_{s}', max_step=0.5, min_width=2.0, min_cuts=4, terminals=[
        dict(name='bond', layer='M5', box=bond), dict(name='feed', layer='M5', box=feed), dict(name='mim', layer='M4', boxes=mb), dict(auto_contacts='hd', window=leg),
        dict(auto_contacts='dio', window=[140, 440, 320, 700])],
        groups=dict(heads=dict(prefix='hd'), heads_1k=dict(prefix='hd', ballast_ohm=1000.), diodes=dict(prefix='dio')),
        pairs=[['bond', 'heads'], ['bond', 'heads_1k'], ['bond', 'mim'], ['bond', 'feed'], ['feed', 'heads'], ['feed', 'heads_1k'], ['feed', 'mim'], ['bond', 'diodes'], ['feed', 'diodes']]))
for s, leg, y, mt in (('P', LEGP, 612.75, mimtop), ('N', LEGN, 618.75, [mir(b) for b in mimtop])):
    nets.append(dict(name=f'RX_{s}', max_step=0.2, terminals=[
        dict(name='pin', layer='M5', box=[491, y - .3, 492, y + .3]), dict(name='mim', layer='M5', boxes=mt), dict(auto_contacts='dev', window=leg)],
        groups=dict(devs=dict(prefix='dev')), pairs=[['pin', 'mim'], ['mim', 'devs'], ['pin', 'devs']]))
nets.append(dict(name='VBIAS', max_step=0.2, terminals=[dict(name='pin', layer='M5', box=[491, 629.75, 492, 630.75]), dict(auto_contacts='rb')],
                 groups=dict(rbP=dict(prefix='rb', window=LEGP), rbN=dict(prefix='rb', window=LEGN)), pairs=[['pin', 'rbP'], ['pin', 'rbN']]))
nets.append(dict(name='VDD', max_step=0.2, terminals=[dict(name='pin', layer='M5', box=[491, 622.25, 492, 623.25]), dict(auto_contacts='d')],
                 groups=dict(devP=dict(prefix='d', window=LEGP), devN=dict(prefix='d', window=LEGN)), pairs=[['pin', 'devP'], ['pin', 'devN']]))
nets.append(dict(name='VSS', clip=[318, 426, 492, 801], max_step=0.4, terminals=[dict(name='pin', layer='M5', box=[491, 608.25, 492, 609.25]),
                 dict(name='shell', layer='M4', box=[329, 426.9, 331, 428.5]), dict(auto_contacts='t')],
                 groups=dict(tapP=dict(prefix='t', window=LEGP), tapN=dict(prefix='t', window=LEGN)), pairs=[['pin', 'tapP'], ['pin', 'tapN'], ['pin', 'shell'], ['shell', 'tapP'], ['shell', 'tapN']]))
print(json.dumps(dict(nets=nets), indent=1))
