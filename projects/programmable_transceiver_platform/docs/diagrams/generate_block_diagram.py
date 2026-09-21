"""Draw the intended transceiver as an editable circuit-block SVG (stdlib only)."""
from pathlib import Path
from html import escape
A=[]
def put(s): A.append(s)
def label(x,y,s,n=19,bold=False,anchor='middle',color='#172a3a'):
    put(f'<text x="{x}" y="{y}" font-size="{n}" font-weight="{600 if bold else 400}" text-anchor="{anchor}" fill="{color}">{escape(s)}</text>')
def rect(x,y,w,h,fill='white',stroke='#233e50',dash=False):
    put(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="2"'+(' stroke-dasharray="8 6"' if dash else '')+'/>')
def wire(points,arrow=True,clock=False):
    d='M '+' L '.join(f'{x},{y}' for x,y in points)
    put(f'<path d="{d}" fill="none" stroke="{"#80549c" if clock else "#233e50"}" stroke-width="2.5"'+(' stroke-dasharray="7 4"' if clock else '')+(' marker-end="url(#arrow)"' if arrow else '')+'/>')
def dot(x,y):put(f'<circle cx="{x}" cy="{y}" r="4" fill="#233e50"/>')
def block(x,y,w,h,title,sub='',fill='white'):
    rect(x,y,w,h,fill);label(x+w/2,y+h/2+(0 if sub else 6),title,20,True)
    if sub:label(x+w/2,y+h/2+24,sub,15)
def amp(x,y,title,sub='',left=False):
    # x,y is center, 100x76 symbol.
    sign=-1 if left else 1
    pts=f'{x-sign*50},{y-38} {x-sign*50},{y+38} {x+sign*50},{y}'
    put(f'<polygon points="{pts}" fill="white" stroke="#233e50" stroke-width="2.5"/>')
    label(x-sign*14,y+7,title,20,True)
    if sub:label(x,y+66,sub,16)
def circ(x,y,op,sub=''):
    put(f'<circle cx="{x}" cy="{y}" r="28" fill="white" stroke="#233e50" stroke-width="2.5"/>')
    label(x,y+10,op,32)
    if sub:label(x,y+62,sub,16)
def converter(x,y,name,left=False):
    sign=-1 if left else 1
    pts=f'{x-sign*60},{y-37} {x+sign*32},{y-37} {x+sign*62},{y} {x+sign*32},{y+37} {x-sign*60},{y+37}'
    put(f'<polygon points="{pts}" fill="white" stroke="#233e50" stroke-width="2.5"/>');label(x-6*sign,y+7,name,22,True)
def filter_(x,y,name='LPF'):
    rect(x-52,y-34,104,68)
    wire([(x-35,y+18),(x-35,y-22)],False);wire([(x-40,y+12),(x+38,y+12)],False)
    wire([(x-30,y-12),(x+8,y-12),(x+29,y+22)],False)
    label(x,y+65,name,16)
def cap(x,y):
    wire([(x,y-18),(x,y-5)],False);wire([(x-12,y-5),(x+12,y-5)],False)
    wire([(x-12,y+5),(x+12,y+5)],False);wire([(x,y+5),(x,y+22)],False)
    wire([(x-12,y+22),(x+12,y+22)],False)
def switch(x,y):
    dot(x-22,y);dot(x+22,y);wire([(x-22,y),(x+15,y-18)],False)
def pin(x,y,w,name,count):
    block(x,y,w,65,name,count,'#f7f9fb')
def panel(x,y,w,h,title,fill):
    rect(x,y,w,h,fill,'#b5c3ce',True);label(x+18,y+29,title,22,True,'start')
put('''<svg xmlns="http://www.w3.org/2000/svg" width="2600" height="2180" viewBox="0 0 2600 2180" role="img" aria-labelledby="title desc"><title id="title">Svalbard circuit-block schematic and approximate placement</title><desc id="desc">Explicit RF I and Q mixer, gain, filter and converter paths; PLL feedback loops; wired equalizer, sampler, CDR and serializer; programmable analog tiles; references and host control. All external terminals are at the perimeter. Intended circuits, not a completed transistor schematic.</desc><defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L9 4 L0 8" fill="#233e50"/></marker></defs><rect width="2600" height="2180" fill="white"/><g font-family="DejaVu Sans,sans-serif">''')
label(55,48,'SVALBARD / CIRCUIT-BLOCK SCHEMATIC',32,True,'start')
label(55,80,'Proposed connectivity with RF west, wired east, clocks north and digital south',21,anchor='start')
label(2540,48,'50 TERMINALS',25,True,'end');label(2540,80,'36 signal + 14 supply / return',19,anchor='end')
rect(200,190,2200,1760,'#fcfdfe','#8196a6')
# external ref and split
pin(1100,110,270,'REF_IN','1 terminal')
block(1145,210,180,58,'REF buffer')
wire([(1235,175),(1235,210)])
wire([(1145,239),(345,239),(345,338)],clock=True)
wire([(1325,239),(1690,239),(1690,338)],clock=True)
# PLLs, explicit forward + feedback
panel(230,285,1120,270,'RF SYNTHESIZER / LOCAL QUADRATURE LO','#f8f3fc')
panel(1500,285,870,270,'WIRED TX SYNTHESIZER','#f8f3fc')
def pll(xs,y,rf):
    p,cp,lf,vco=xs
    block(p-45,y-32,90,64,'PFD');block(cp-45,y-32,90,64,'CP','±I')
    block(lf-65,y-32,130,64,'R–C filter','Cf / R / Cs')
    circ(vco,y,'~','VCO')
    for a,b in [(p+45,cp-45),(cp+45,lf-65),(lf+65,vco-28)]:wire([(a,y),(b,y)])
    # A clearly separate feedback return at the bottom of the loop.
    dv=(cp+lf)/2;block(dv-65,y+103,130,53,'÷ N','feedback')
    wire([(vco+36,y),(vco+36,y+130),(dv+65,y+130)])
    wire([(dv-65,y+130),(p,y+130),(p,y+32)])
    dot(vco+36,y)
    return vco+36
pll((345,535,745,970),370,True)
block(1125,338,180,64,'I/Q phases','0° / 90° buffers')
wire([(998,370),(1125,370)])
label(1160,475,'LO-I',19,True,color='#80549c');label(1270,475,'LO-Q',19,True,color='#80549c')
wire([(1160,402),(1160,446)],clock=True);wire([(1270,402),(1270,446)],clock=True)
pll((1690,1835,2020,2190),370,False)
wire([(2218,370),(2320,370),(2320,470)],clock=True);label(2310,498,'CLK-TX',18,True,color='#80549c')
# RF RX panel and edge
panel(230,585,1120,430,'RF RX — I AND Q ARE SEPARATE CIRCUITS','#f1f8f5')
pin(15,687,180,'RF_RX_P/N','2 terminals')
block(255,687,130,65,'ESD / match','bias / input')
wire([(195,720),(255,720)])
amp(465,720,'G','LNA');wire([(385,720),(415,720)])
wire([(515,720),(550,720)],False);dot(550,720)
for y,ch,lo in [(695,'I','LO-I'),(905,'Q','LO-Q')]:
    wire([(550,720),(550,y),(612,y)])
    circ(640,y,'×');label(640,y-52,lo,17,True,color='#80549c');wire([(640,y-40),(640,y-28)],clock=True)
    amp(770,y,'G',f'{ch} PGA');wire([(668,y),(720,y)])
    filter_(930,y,'R/C or gm-C LPF');wire([(820,y),(878,y)])
    switch(1040,y);wire([(982,y),(1018,y)]);cap(1075,y+40)
    wire([(1062,y),(1110,y)]);dot(1075,y);wire([(1075,y),(1075,y+22)],False)
    converter(1170,y,'A/D');label(1170,y+88,f'{ch}: CDAC / comparator / SAR',15)
    wire([(1232,y),(1310,y)]);label(1285,y-16,f'RX-{ch}',16,True)
    # Low bandwidth offset servo back to PGA input.
    wire([(845,y),(845,y+94),(790,y+94)],False);dot(845,y)
    block(690,y+73,100,42,'∫ / trim')
    wire([(690,y+94),(680,y+94),(680,y+23),(720,y+23)])

# RF TX split explicit DAC and reconstruction
panel(230,1040,1120,410,'RF TX — SEPARATE I/Q RECONSTRUCTION AND MIXERS','#f1f8f5')
pin(15,1208,180,'RF_TX_P/N','2 terminals')
block(255,1208,110,65,'ESD / bias')
amp(450,1240,'G','RF driver',True);wire([(400,1240),(365,1240)]);wire([(255,1240),(195,1240)])
circ(560,1240,'Σ');wire([(532,1240),(500,1240)])
for y,ch,lo in [(1150,'I','LO-I'),(1350,'Q','LO-Q')]:
    wire([(560,y),(560,1212 if y<1240 else 1268)])
    circ(675,y,'×');wire([(647,y),(560,y)],False)
    label(675,y-49,lo,17,True,color='#80549c');wire([(675,y-39),(675,y-28)],clock=True)
    amp(810,y,'G',f'{ch} gain',True);wire([(760,y),(703,y)])
    filter_(980,y,'Reconstruction LPF');wire([(928,y),(860,y)])
    converter(1180,y,'D/A',True);wire([(1118,y),(1032,y)])
    label(1180,y+64,f'{ch}: cells + update latch',16)
    wire([(1320,y),(1240,y)]);label(1285,y-16,f'TX-{ch}',16,True)

# wired RX
panel(1500,585,870,430,'WIRED RX — CONTINUOUS LINE-RATE PATH','#f2f5fc')
pin(2405,657,180,'WIRE_RX_P/N','2 terminals')
block(2220,657,125,65,'ESD / Rterm','CM bias');wire([(2405,690),(2345,690)])
filter_(2130,690,'CTLE boost');wire([(2220,690),(2182,690)])
amp(1980,690,'G','VGA / offset',True);wire([(2078,690),(2030,690)])
amp(1810,690,'±','Slicer',True);wire([(1930,690),(1860,690)])
block(1540,658,150,64,'D / Q','sampler bank');wire([(1760,690),(1690,690)])
block(1540,790,170,65,'Deserializer','align / elastic');wire([(1615,722),(1615,790)])
block(1780,825,130,65,'Phase det.');block(1960,825,130,65,'Loop filter')
block(2140,825,180,65,'Phase control','local oscillator / PI')
wire([(1735,690),(1735,857),(1780,857)]);dot(1735,690)
wire([(1910,857),(1960,857)]);wire([(2090,857),(2140,857)])
wire([(2230,890),(2230,949),(1518,949),(1518,750),(1580,750),(1580,722)],clock=True)
label(1910,977,'Recovered sampling phase → sampler bank (CLK-RX)',16,color='#80549c')
# fix phase destination route using tag: reference clock feeds sampler through tag
label(1605,630,'CLK-RX',17,True,color='#80549c');wire([(1615,635),(1615,658)],clock=True)
# wired TX
panel(1500,1040,870,410,'WIRED TX — SERIALIZE, SHAPE, DRIVE','#f2f5fc')
pin(2405,1208,180,'WIRE_TX_P/N','2 terminals')
block(1540,1130,155,70,'TX word FIFO','gearbox / PRBS')
block(1760,1130,160,70,'Serializer','mux / retime')
wire([(1695,1165),(1760,1165)])
label(1840,1099,'CLK-TX',17,True,color='#80549c');wire([(1840,1105),(1840,1130)],clock=True)
block(1760,1290,160,60,'z⁻¹','tap delay')
wire([(1950,1165),(1950,1255),(1730,1255),(1730,1320),(1760,1320)]);dot(1950,1165)
amp(2050,1165,'a₀','Main tap');wire([(1920,1165),(2000,1165)])
amp(2050,1320,'a₁','Postcursor');wire([(1920,1320),(2000,1320)])
circ(2180,1240,'Σ');wire([(2100,1165),(2180,1165),(2180,1212)])
wire([(2100,1320),(2180,1320),(2180,1268)])
amp(2290,1240,'G','Line driver');wire([(2208,1240),(2240,1240)]);wire([(2340,1240),(2405,1240)])
block(2220,1343,120,64,'Sense / idle','detect current')
wire([(2360,1240),(2360,1375),(2340,1375)]);dot(2360,1240)
label(1540,1420,'Idle gates driver bias; detect current senses the output load',15,anchor='start')
# lower analog services
panel(230,1480,700,205,'LOCAL ANALOG TILE / SLOW DIAGNOSTICS','#fbf8ed')
switch(285,1575);wire([(255,1575),(263,1575)]);amp(400,1575,'gm','Weight / sign');wire([(307,1575),(350,1575)])
circ(525,1575,'Σ');wire([(450,1575),(497,1575)]);amp(655,1575,'∫','C integration');wire([(553,1575),(605,1575)])
amp(820,1575,'±','Compare / sample');wire([(705,1575),(770,1575)])
label(575,1661,'Local topology switches; buffered diagnostic mux → shared ADC by ownership',16)
panel(960,1480,730,205,'BIAS / CONVERTER REFERENCE SERVICES','#fbf8ed')
block(982,1540,145,70,'V / I ref','startup + trim')
amp(1220,1575,'A','Error amp');wire([(1127,1575),(1170,1575)])
block(1320,1540,135,70,'Source / sink','buffer')
wire([(1270,1575),(1320,1575)]);wire([(1455,1575),(1620,1575)])
cap(1530,1610);dot(1530,1575);wire([(1530,1575),(1530,1592)],False)
wire([(1490,1575),(1490,1518),(1220,1518),(1220,1537)]);dot(1490,1575)
label(1580,1545,'VREF',18,True);label(1515,1662,'Local copies / RC decoupling',16)
panel(1720,1480,650,205,'CLOCK / SAFETY / OBSERVATION','#f8f3fc')
block(1740,1540,170,70,'÷ / phase','ADC / DAC clocks')
block(1940,1540,175,70,'Lock / reset','gating / release')
block(2145,1540,200,70,'Slow monitor mux','idle / amplitude / trim')
label(2040,1658,'Named clock nets are buffered locally; no global GHz analog crossbar',16)
# digital along bottom
block(230,1730,550,175,'RF data / memory / CDC','I/Q queues · capture / playback · update sequencing','#f0f3f7')
block(810,1730,700,175,'Shared control / framing / resource ownership','SPI · calibration · atomic run / stop · fault / epoch recovery','#f0f3f7')
block(1540,1730,830,175,'Wired words / GPIO PHY / clock alignment','Queues · raw/bypass · DDR capture / launch · local HOST_A / HOST_B rails','#f0f3f7')
# Matched net labels keep digital buses distinct and off sensitive analog nodes.
label(505,1712,'RX-I / RX-Q ↓    TX-I / TX-Q ↑',18,True)
wire([(1540,825),(1470,825)],False);label(1460,805,'RX-W',16,True)
label(1600,1100,'TX-W',16,True);wire([(1600,1105),(1600,1130)])
label(1940,1712,'RX-W ↓    TX-W ↑     H2D / D2H',18,True)
wire([(780,1820),(810,1820)]);wire([(1510,1820),(1540,1820)])
# external pins bottom for 22 host + 5 ctl + 14power =41, plus8analog+1ref=50
pin(250,1970,525,'H2D_D[9:0] + H2D_CLK','11 terminals → input capture / DDR')
pin(825,1970,525,'D2H_D[9:0] + D2H_CLK','11 terminals ← launch / DDR')
pin(1400,1970,450,'SPI (4) + RESET_N (1)','5 terminals · independent recovery')
pin(1900,1970,475,'SUPPLIES / RETURNS','14 terminals · 7 local supply / return pairs')
wire([(510,1970),(510,1930)]);label(510,1924,'H2D → GPIO PHY',16,True)
wire([(1100,1930),(1100,1970)]);label(1100,1924,'D2H ← GPIO PHY',16,True)
wire([(1625,1970),(1625,1930),(1250,1930),(1250,1905)])
label(55,2080,'Symbols: G/A = gain/error amplifier; × = mixer; Σ = sum; ∫ = integration; ± = comparator; D/Q = sampling latch.',19,anchor='start')
label(55,2115,'Differential pairs use one line; I/Q paths remain separate. Matching RX/TX and clock labels connect nets. No wire crossing implies a connection without a dot.',18,anchor='start')
label(55,2150,'Intended architecture, not a wired transistor schematic or area proof. Placement is approximate; supplies fan out locally. PA, antenna and protocol/modem logic remain external.',18,anchor='start')
put('</g></svg>')
Path(__file__).with_name('transceiver-block-diagram.svg').write_text('\n'.join(A)+'\n')
