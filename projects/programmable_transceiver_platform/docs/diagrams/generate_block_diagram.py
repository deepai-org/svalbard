"""Draw the intended transceiver as an editable circuit-block SVG (stdlib only)."""
from pathlib import Path
from html import escape
A=[]
WIRE_COLOR=None
def put(s): A.append(s)
def label(x,y,s,n=19,bold=False,anchor='middle',color='#172a3a'):
    put(f'<text x="{x}" y="{y}" font-size="{n}" font-weight="{600 if bold else 400}" text-anchor="{anchor}" fill="{color}">{escape(s)}</text>')
def rect(x,y,w,h,fill='white',stroke='#233e50',dash=False):
    put(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="2"'+(' stroke-dasharray="8 6"' if dash else '')+'/>')
def wire(points,arrow=True,clock=False):
    d='M '+' L '.join(f'{x},{y}' for x,y in points)
    put(f'<path d="{d}" fill="none" stroke="{WIRE_COLOR or ("#80549c" if clock else "#233e50")}" stroke-width="2.5"'+(' stroke-dasharray="7 4"' if clock else '')+(' marker-end="url(#arrow)"' if arrow else '')+'/>')
def dot(x,y):put(f'<circle cx="{x}" cy="{y}" r="4" fill="#233e50"/>')
def block(x,y,w,h,title,sub='',fill='white'):
    rect(x,y,w,h,fill);label(x+w/2,y+h/2+(0 if sub else 6),title,min(20, int(w / max(1, len(title)) / .58)),True)
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
put('''<svg xmlns="http://www.w3.org/2000/svg" width="2600" height="30000" viewBox="0 0 2600 30000" role="img" aria-labelledby="title desc"><title id="title">Svalbard circuit-block schematic and approximate placement</title><desc id="desc">Explicit RF I and Q mixer, gain, filter and converter paths; PLL feedback loops; wired equalizer, sampler, CDR and serializer; programmable analog tiles; references and host control. All external terminals are at the perimeter. Intended circuits, not a completed transistor schematic.</desc><defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L9 4 L0 8" fill="#233e50"/></marker></defs><rect width="2600" height="30000" fill="white"/><g font-family="DejaVu Sans,sans-serif">''')
label(55,48,'SVALBARD / CIRCUIT-BLOCK SCHEMATIC',32,True,'start')
label(55,80,'Proposed connectivity with RF west, wired east, clocks north and digital south',21,anchor='start')
label(2540,48,'50 TERMINALS',25,True,'end');label(2540,80,'36 signal + 14 supply / return',19,anchor='end')
label(55,120,'RF OR WIRED PAYLOAD ACTIVE — not simultaneous',19,True,'start')
label(55,150,'Shared services; further analog / clock sharing under evaluation',17,anchor='start')
rect(120,190,2280,1920,'#fcfdfe','#8196a6')
# external ref and split
pin(1100,110,270,'REF_IN','1 terminal')
block(1145,210,180,58,'REF buffer')
wire([(1235,175),(1235,210)])
wire([(1145,239),(345,239),(345,338)],clock=True)
wire([(1325,239),(1690,239),(1690,338)],clock=True)
# PLLs, explicit forward + feedback
panel(230,285,1120,270,'RF SYNTHESIZER / LOCAL QUADRATURE LO','#f8f3fc')
panel(1500,285,870,270,'WIRED TX SYNTH / RATE BANKS','#f8f3fc')
def pll(xs,y,rf):
    p,cp,lf,vco=xs
    block(p-45,y-32,90,64,'PFD');block(cp-45,y-32,90,64,'CP','±I')
    block(lf-65,y-32,130,64,'R–C filter','3 nodes (RF)' if rf else 'Cf / R / Cs')
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
    filter_(930,y,'LPF bank; 9.16 MHz base');wire([(820,y),(878,y)])
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
pin(2405,657,180,'WIRE_RX_P/N','USB D+/D- in USB mode')
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
wire([(2230,890),(2230,915),(1518,915),(1518,750),(1580,750),(1580,722)],clock=True)
label(1910,936,'Recovered sampling phase → sampler bank (CLK-RX)',16,color='#80549c')
# fix phase destination route using tag: reference clock feeds sampler through tag
# Sampled decisions are a second, distinct input to the phase detector.
wire([(1615,760),(1750,760),(1750,805),(1830,805),(1830,825)])
dot(1615,760)
label(1800,793,'Decisions',14)
label(1605,630,'CLK-RX',17,True,color='#80549c');wire([(1615,635),(1615,658)],clock=True)
# USB circuitry remains local to the wired RX pad pair.
block(1995,944,300,32,'USB HS / FS / LS branch')
wire([(2378,690),(2378,960),(2295,960)],False);dot(2378,690)
wire([(2378,690),(2405,690)],False)
label(2160,1010,'Local bidirectional path; detail on final sheet',14)
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
# Extra routing band separates high-speed circuits from shared services.
put('<g transform="translate(0,160)">')
# lower analog services
panel(230,1480,700,205,'LOCAL ANALOG TILE / SLOW DIAGNOSTICS','#fbf8ed')
switch(325,1575);wire([(347,1575),(350,1575)],False);amp(400,1575,'gm','Weight / sign');
circ(525,1575,'Σ');wire([(450,1575),(497,1575)]);amp(655,1575,'∫','C integration');wire([(553,1575),(605,1575)])
amp(820,1575,'±','Compare / sample');wire([(705,1575),(770,1575)])
label(595,1653,'Programmable local chain → diagnostic mux',15)
panel(960,1480,730,205,'BIAS / CONVERTER REFERENCE SERVICES','#fbf8ed')
block(982,1540,145,70,'V / I ref','startup + trim')
amp(1220,1575,'A','Error amp');wire([(1127,1575),(1170,1575)])
block(1320,1540,135,70,'Source / sink','buffer')
wire([(1270,1575),(1320,1575)]);wire([(1455,1575),(1620,1575)])
cap(1530,1610);dot(1530,1575);wire([(1530,1575),(1530,1592)],False)
wire([(1490,1575),(1490,1518),(1220,1518),(1220,1537)]);dot(1490,1575)
label(1580,1545,'VREF',18,True);label(1505,1622,'Local copies / RC decoupling',14)
panel(1720,1480,650,205,'CLOCK / SAFETY / OBSERVATION','#f8f3fc')
block(1740,1540,170,70,'÷ / phase','ADC / DAC clocks')
block(1940,1540,175,70,'Lock / reset','gating / release')
block(2145,1540,200,70,'Slow monitor mux','idle / amplitude / trim')
label(2040,1624,'Buffered clocks / isolated observations',14)
# digital along bottom
block(230,1730,550,175,'RF data / memory / CDC','I/Q queues · capture / playback · update sequencing','#f0f3f7')
block(810,1730,700,175,'Shared control / framing / resource ownership','SPI · calibration · atomic run / stop · fault / epoch recovery','#f0f3f7')
block(1540,1730,830,175,'Wired words / GPIO PHY / clock alignment','Queues · raw/bypass · DDR capture / launch · local HOST_A / HOST_B rails','#f0f3f7')
# Local word ports connect to the detailed buses drawn below.




wire([(780,1820),(810,1820)]);wire([(1510,1820),(1540,1820)])
# external pins bottom for 22 host + 5 ctl + 14power =41, plus8analog+1ref=50
pin(250,1970,525,'H2D_D[9:0] + H2D_CLK','11 terminals → input capture / DDR')
pin(825,1970,525,'D2H_D[9:0] + D2H_CLK','11 terminals ← launch / DDR')
pin(1400,1970,450,'SPI (4) + RESET_N (1)','5 terminals · independent recovery')
pin(1900,1970,475,'SUPPLIES / RETURNS','14 terminals · 7 local supply / return pairs')
wire([(510,1970),(510,1945),(1730,1945),(1730,1905)])
wire([(1820,1905),(1820,1957),(1100,1957),(1100,1970)])
wire([(1625,1970),(1625,1930),(1250,1930),(1250,1905)])
wire([(1300,1905),(1300,1920),(1660,1920),(1660,1970)])
label(55,2080,'Symbols: G/A = gain/error amplifier; × = mixer; Σ = sum; ∫ = integration; ± = comparator; D/Q = sampling latch.',19,anchor='start')
label(55,2115,'Differential pairs and digital words use bundled lines. Junction dots connect; crossings without dots do not. Purple: clocks. Orange: reference. Blue: control.',18,anchor='start')
label(55,2150,'Panel service ports distribute configuration, bias and supply locally to their enclosed circuits. No implied global analog crossbar. This is not a transistor netlist or layout.',18,anchor='start')
put('</g>')
# Explicit buses, each with its own track; no I/Q shorts.
for y,track,rail,left,foot,port,rx,name in [
    (695,1365,1490,145,1850,350,True,'RX-I'),
    (905,1380,1510,160,1860,450,True,'RX-Q'),
    (1150,1395,1530,175,1870,550,False,'TX-I'),
    (1350,1410,1550,190,1880,650,False,'TX-Q')]:
    points=[(1310 if rx else 1320,y),(track,y),(track,rail),(left,rail),(left,foot),(port,foot),(port,1890)]
    wire(points if rx else list(reversed(points)))
    label(320,rail-6,name+' sample bus',15,True,anchor='start')
wire([(1540,825),(1460,825),(1460,1590),(1705,1590),(1705,1870),(1800,1870),(1800,1890)])
wire([(1850,1890),(1850,1880),(2385,1880),(2385,1110),(1600,1110),(1600,1130)])
# Shared LO distribution, with distinct I/Q branches to both RF mixers.
for source,trunk,rx_y,tx_y in [(1160,595,655,1111),(1270,605,865,1311)]:
    outer=1356 if source==1160 else 1360; shelf=620 if source==1160 else 632
    wire([(source,446),(source,565 if source==1160 else 575),(outer,565 if source==1160 else 575),(outer,shelf),(trunk,shelf),(trunk,1025 if source==1160 else 1030),(1372 if source==1160 else 1378,1025 if source==1160 else 1030),(1372 if source==1160 else 1378,tx_y),(675,tx_y)],False,True)
    wire([(trunk,rx_y),(640,rx_y)],False,True);dot(trunk,rx_y)
# TX serializer clock from its PLL; distribute outside the wired island.
wire([(2320,470),(2395,470),(2395,1025),(1840,1025),(1840,1105)],False,True)
# Buffered master reference to sample-clock generation (service strip).
wire([(1325,239),(1440,239),(1440,1615),(1825,1615),(1825,1700)],True,True)
label(1750,1605,'REF → sample-clock divider',16)
# Sample clocks split to ADC sampling switches and DAC update latches.
wire([(1825,1770),(1825,1815),(1430,1815),(1430,1020),(1090,1020),(1090,640)],False,True)
for y in (695,905):
    wire([(1090,y-55),(1040,y-55),(1040,y-18)],True,True);dot(1090,y-55)
wire([(1430,1020),(1335,1020),(1335,1405)],False,True)
for y in (1150,1350):
    wire([(1335,y+38),(1200,y+38),(1200,y+30)],True,True);dot(1335,y+38)
dot(1430,1020)
# VREF fanout to separate ADC and DAC reference terminals.
WIRE_COLOR='#b47a20'
wire([(1620,1735),(1680,1735),(1680,1627),(1347,1627),(1347,645)],False)
for y in (695,905,1150,1350):
    wire([(1347,y-44),(1180,y-44),(1180,y-37)]);dot(1347,y-44)
WIRE_COLOR=None
# Each island has an explicit service port. A bundled configuration bus avoids
# pretending that all trim bits and supply nets are one electrical conductor.
WIRE_COLOR='#386991'
wire([(1460,1890),(1460,1865),(2418,1865),(2418,275),(225,275),(225,1865),(850,1865),(850,1890)],False)
for x,y,edge in [(230,520,225),(230,995,225),(230,1430,225),(2370,520,2418),(2370,995,2418),(2370,1430,2418)]:
    wire([(edge,y),(x,y)]);dot(edge,y)
    label(x+8 if edge==225 else x-8,y-9,'CTRL / BIAS',13,True,'start' if edge==225 else 'end',color='#386991')
label(1520,273,'CONFIGURATION / TRIM / ENABLE / STATUS BUS',16,True,anchor='start')
WIRE_COLOR=None
# Supply terminal bundle feeds a local-domain distribution bar, never the data bus.
wire([(2135,2130),(2135,2080),(2460,2080),(2460,255),(210,255),(210,1600)],False)
label(1810,248,'7 SUPPLY / RETURN PAIRS → LOCAL DOMAIN FEEDS',15,True,anchor='start')
for y in (535,1008,1445):
    wire([(210,y),(230,y)]);dot(210,y)
    wire([(2460,y),(2370,y)]);dot(2460,y)
wire([(210,1600),(1050,1600),(1050,1700)])
# Diagnostic source selection is analog; status output is a separate digital port.
wire([(2280,1407),(2280,1580),(2320,1580),(2320,1700)])
label(2268,1570,'Buffered TX sense',15)
# Local programmable tile receives a selected DAC observation through a buffer.
wire([(1070,1350),(1070,1465),(960,1465),(960,1605),(250,1605),(190,1605),(190,1735),(200,1735)]);dot(1070,1350)
amp(250,1735,'1','Probe buffer')
wire([(300,1735),(303,1735)],False)
# Tile comparator output to slow monitor mux; its decision also has a status path.
wire([(870,1735),(945,1735),(945,1620),(2260,1620),(2260,1700)])
wire([(2345,1735),(2360,1735),(2360,1853),(1400,1853),(1400,1890)])
wire([(2030,1770),(2030,1830),(1340,1830),(1340,1890)])
label(2160,1845,'MON / LOCK status',15)
# Analog diagnostic output is routed to an explicit source-selection switch
# ahead of the I-channel sample/hold; selection excludes simultaneous RF-I use.
WIRE_COLOR='#a06b20'
wire([(2145,1750),(2125,1750),(2125,1638),(1420,1638),(1420,805),(1000,805),(1000,715)],False)
wire([(1000,715),(1000,695)],False)
rect(989,684,22,22,'white','#a06b20');label(1000,701,'S',14,True)
label(1090,817,'S: RF-I / diagnostic select',14)
WIRE_COLOR=None

# Connection-detail sheet. Named ports connect to the same names in the overview;
# this exposes internal interfaces without routing every control bit across RF.
label(55,2380,'CONNECTION DETAILS / REPEATED CHANNELS AND SHARED SERVICES',29,True,'start')
label(55,2415,'Named ports are connections to the overview. I and Q instances are independent; these are intended circuit interfaces.',19,anchor='start')
def port(x,y,name,above=True):
    dot(x,y);label(x,y-12 if above else y+25,name,16,True)
panel(55,2450,1210,425,'SAR ADC × 2 — ONE INSTANCE PER I / Q CHANNEL','#f1f8f5')
block(90,2560,150,65,'Input mux','diagnostic: I only')
switch(310,2592);wire([(240,2592),(288,2592)])
block(390,2560,180,65,'CDAC / hold','sample + bit trials')
wire([(332,2592),(390,2592)])
amp(680,2592,'±','Comparator');wire([(570,2592),(630,2592)])
block(830,2560,175,65,'SAR sequencer','trial / decide / latch');wire([(730,2592),(830,2592)])
block(1060,2560,160,65,'Result latch','RX-I / RX-Q');wire([(1005,2592),(1060,2592)])
wire([(915,2625),(915,2750),(480,2750),(480,2625)])
label(675,2740,'Trial code → capacitor switches',17)
wire([(1140,2625),(1140,2800),(1215,2800)]);port(1215,2800,'RX_VALID',False)
wire([(90,2592),(75,2592)],False);port(165,2530,'RF-I / RF-Q');wire([(165,2530),(165,2560)])
wire([(310,2505),(310,2574)],clock=True);port(310,2505,'SAMPLE')
wire([(915,2505),(915,2560)],clock=True);port(915,2505,'SAR_STEP / RESET')
WIRE_COLOR='#b47a20'
wire([(480,2505),(480,2560)]);port(480,2505,'VREF± / VCM')
wire([(680,2680),(680,2630)]);port(680,2680,'VCM / CMP_TRIM',False)
WIRE_COLOR=None
label(90,2845,'SAR_STEP requires a local conversion clock; its implementation and rate remain to be qualified.',16,anchor='start')
panel(1300,2450,1245,425,'DAC × 2 — ONE INSTANCE PER I / Q CHANNEL','#f1f8f5')
block(1340,2560,180,65,'TX word queue','TX-I / TX-Q')
block(1600,2560,170,65,'Shadow latch','pending code')
block(1860,2560,180,65,'Active latch','atomic update')
block(2140,2560,170,65,'DAC array','weighted cells')
amp(2440,2592,'A','Output buffer')
for a,b in [(1520,1600),(1770,1860),(2040,2140),(2310,2390)]:wire([(a,2592),(b,2592)])
wire([(2490,2592),(2515,2592)]);port(2410,2680,'TO RECONSTRUCTION LPF',False)
wire([(2515,2592),(2515,2680),(2410,2680)],False)
wire([(1685,2505),(1685,2560)],clock=True);port(1685,2505,'WORD_VALID / LOAD')
wire([(1950,2505),(1950,2560)],clock=True);port(1950,2505,'DAC_UPDATE')
WIRE_COLOR='#b47a20'
wire([(2225,2505),(2225,2560)]);port(2225,2505,'VREF± / IBIAS')
WIRE_COLOR=None
wire([(1950,2625),(1950,2770),(1430,2770),(1430,2625)])
label(1700,2760,'Update consumed → queue advance',17)
label(1340,2845,'Underrun / idle selects a configured safe code; mode changes invalidate pending words.',16,anchor='start')
panel(55,2910,1210,385,'CLOCK QUALIFICATION / ENABLES / CALIBRATION','#f8f3fc')
block(90,3000,190,65,'REF counter','reference present')
block(370,3000,215,65,'Lock qualifier','RF / wired / CDR')
block(680,3000,200,65,'Run controller','reset / arm / fault')
block(975,3000,235,65,'Local clock gates','sample / update / TX')
for a,b in [(280,370),(585,680),(880,975)]:wire([(a,3032),(b,3032)])
port(185,2980,'REF_IN');wire([(185,2980),(185,3000)],clock=True)
port(477,2980,'PLL / CDR OBS');wire([(477,2980),(477,3000)],clock=True)
block(90,3160,220,65,'Calibration FSM','request / compare')
block(425,3160,220,65,'Trim registers','bias / offset / tune')
block(810,3160,400,65,'Comparator / monitor selection','buffered local observation')
wire([(310,3192),(425,3192)])
wire([(810,3192),(710,3192),(710,3260),(200,3260),(200,3225)])
label(450,3250,'Decision / valid → next trim trial',16)
wire([(780,3065),(780,3115),(200,3115),(200,3160)])
label(450,3104,'Quiet grant / converter ownership',16)
wire([(535,3160),(535,3135),(1010,3135),(1010,3160)])
label(890,3125,'Target / observation select',16)
wire([(535,3225),(535,3280),(690,3280)]);label(850,3285,'TRIM → analog target',15)
panel(1300,2910,1245,385,'SUPPLY / RETURN / BIAS DISTRIBUTION','#fbf8ed')
block(1340,3000,220,65,'Supply pads × 7','paired local returns')
block(1650,3000,240,65,'Local decoupling','domain supply / return')
block(2020,3000,475,65,'Domain consumers','RF · wired · clocks · analog · digital · host')
wire([(1560,3032),(1650,3032)]);wire([(1890,3032),(2020,3032)])
block(1340,3160,220,65,'Startup + V/I ref','trim / startup enable')
block(1680,3160,250,65,'Reference buffers','local RC isolation')
block(2090,3160,405,65,'Separate reference / bias loads','ADC · DAC · PGA · mixer · VCO')
wire([(1450,3065),(1450,3160)])
WIRE_COLOR='#b47a20'
wire([(1560,3192),(1680,3192)]);wire([(1930,3192),(2090,3192)])
WIRE_COLOR=None
label(1320,3267,'Supply/return bundles are distinct nets; local regulation is conditional, not an assumed qualified LDO.',16,anchor='start')
panel(55,3330,2490,375,'INTERFACE CONNECTION REGISTER — BUNDLES EXPANDED BY FUNCTION','#f0f3f7')
rows=[
('RF sample transport','ADC-I/Q → result valid + sample words → RX queues → formatter → D2H DDR launch → D2H_D[9:0], D2H_CLK'),
('RF transmit transport','H2D_D[9:0], H2D_CLK → DDR capture → deframer → TX queues → I/Q shadow latches → DAC_UPDATE → DAC arrays'),
('Wired receive / transmit','Slicer → sampler → deserializer → RX queue → D2H; H2D → TX queue → serializer → main + delayed taps → line driver'),
('SPI and reset','SCLK, CS_N, MOSI → register/control engine; status/readback → MISO; RESET_N → reset synchronization → local state resets'),
('Configuration fanout','Registers → gain / filter tuning / mux select / divider ratio / current trim / termination / driver taps / idle / enables'),
('Status return','PLL lock / reference present / CDR status / queue flags / detect result / comparator result → synchronized status → SPI / host framing'),
('Local observation','Buffered selected analog source → tile / monitor mux → RF-I diagnostic selector → I ADC; tile comparator → calibration / status'),
('Clock feedback','RF and wired VCO → programmable feedback divider → PFD → charge pump → R–C loop filter → VCO; CDR phase feedback is separate')]
for i,(name,detail) in enumerate(rows):
    y=3395+i*38
    label(80,y,name,17,True,'start');label(405,y,detail,16,anchor='start')
label(55,3760,'Connectivity intent, not electrical signoff: bus widths, clock-domain synchronizers, switch circuits and analog component values require schematic refinement.',18,anchor='start')

# Expanded wiring sheets: repeated names are electrically identical bundled ports.
label(55,3840,'TRANSPORT WIRING / CLOCK DOMAINS / LOCAL SERVICE CONNECTIONS',29,True,'start')
label(55,3875,'Arrows show transfer direction. DATA includes valid; blue reverse paths carry ready / credit. Named nets join sheets without extra pins.',18,anchor='start')
panel(55,3910,2490,490,'FOUR CONTINUOUS STREAMS — EXPLICIT ROUTING AND CDC','#f0f3f7')
# Independent RF-I/Q words retain pairing inside RF queues; never short analog nets.
for y,title,source,sink in [(4020,'RF receive','RX-I / RX-Q','RF RX queue'),(4230,'Wired receive','Deserializer','WIRE RX queue')]:
    block(85,y,210,65,source,'word + valid')
    block(385,y,230,65,sink,'pair / overflow flags' if y==4020 else 'word / overflow flags')
    block(715,y,240,65,'Async FIFO','write: source / read: host')
    wire([(295,y+32),(385,y+32)]);wire([(615,y+32),(715,y+32)])
    wire([(955,y+32),(1020,y+32),(1020,4157 if y==4020 else 4187),(1090,4157 if y==4020 else 4187)])
    label(405,y-15,title,17,True,anchor='start')
    label(835,y+100,'Gray pointers ↔ sync',16)
block(1090,4140,215,65,'RX scheduler','RF + wired + events')
block(1390,4140,210,65,'Frame / pack','counts + sequence')
block(1690,4140,230,65,'DDR launch','data + forwarded clock')
block(2220,4140,280,65,'D2H_D[9:0] / CLK','edge I/O: 11 terminals')
for a,b in [(1305,1390),(1600,1690),(1920,2220)]:wire([(a,4172),(b,4172)])

WIRE_COLOR='#386991'
wire([(1195,4140),(1195,3980),(835,3980),(835,4020)])
wire([(1215,4140),(1215,4210),(835,4210),(835,4230)])
label(880,3968,'Read RF / read wired (separate grants)',16,color='#386991')
WIRE_COLOR=None
label(1330,4295,'CLK-HOST-TX → scheduler / packer / launch / forwarded D2H_CLK',17,anchor='start',color='#80549c')
label(1330,4330,'Source clocks: ADC_RESULT for RF; CLK-RX for wired.',17,anchor='start')
label(90,4365,'Sources cannot be backpressured at the analog input: overflow records a fault / discontinuity; queue sizing and host service remain requirements.',17,anchor='start')

panel(55,4430,2490,465,'HOST TO ANALOG — DEMULTIPLEX, BUFFER, CONSUME','#f0f3f7')
block(90,4570,265,65,'H2D_D[9:0] / CLK','edge I/O: 11 terminals')
block(415,4570,205,65,'DDR capture','H2D clock / alignment')
block(690,4570,205,65,'Deframe / route','stream ID / commands')
for a,b in [(355,415),(620,690)]:wire([(a,4602),(b,4602)])
for y,title,sink in [(4510,'RF TX FIFO × I/Q','TX-I / TX-Q'),(4740,'WIRE TX FIFO','TX word FIFO')]:
    wire([(895,4602),(960,4602),(960,y+32),(1030,y+32)])
    block(1030,y,245,65,title,'async pointers / epoch')
    block(1380,y,235,65,'Playback select','host / memory / PRBS')
    block(1730,y,265,65,sink,'local consume / valid')
    block(2185,y,315,65,'DAC latches' if y==4510 else 'Serializer','DAC_UPDATE' if y==4510 else 'CLK-TX / word enable')
    for a,b in [(1275,1380),(1615,1730),(1995,2185)]:wire([(a,y+32),(b,y+32)])
    WIRE_COLOR='#386991'
    wire([(2340,y+65),(2340,y+112),(1150,y+112),(1150,y+65)])
    label(1745,y+103,'Consumed / request → queue advance',16,color='#386991')
    WIRE_COLOR=None
    label(1497,y-15,'MEM_TX_RF' if y==4510 else 'MEM_TX_WIRE',16,True,color='#386991')
    wire([(1497,y-10),(1497,y)])
dot(960,4602)
label(90,4818,'FIFO writes: H2D domain.',17,anchor='start')
label(90,4850,'Reads: local DAC / wired domain.',17,anchor='start')

panel(55,4925,1210,635,'CONTROL / MEMORY / CALIBRATION — SEPARATE REQUEST AND RETURN','#edf4fb')
block(85,5020,205,65,'SPI pad engine','SCLK / CS_N / MOSI')
block(385,5020,250,65,'Register bridge','request / ack CDC')
block(760,5020,450,65,'Shadow configuration / commit','ownership / quiet / epoch / reset')
wire([(290,5052),(385,5052)]);wire([(635,5052),(760,5052)])
WIRE_COLOR='#386991'
wire([(760,5085),(735,5085),(735,5130),(187,5130),(187,5085)])
label(550,5120,'Readback → MISO',16,color='#386991')
WIRE_COLOR=None
block(85,5210,230,65,'Capture / playback','banked memory arbiter')
block(405,5210,230,65,'Calibration FSM','trial / settle / observe')
block(760,5210,450,65,'Per-island configuration latches','gain / RC / mux / bias / divider / idle')
wire([(985,5085),(985,5210)])
wire([(850,5170),(520,5170),(520,5210)]);dot(850,5170)
wire([(850,5170),(850,5085)],False)
wire([(450,5085),(450,5148),(335,5148),(335,5190),(200,5190),(200,5210)])
label(200,5180,'SPI memory access*',15)
wire([(635,5242),(760,5242)])
block(85,5400,230,65,'Status CDC','lock / fault / idle / flags')
block(405,5400,230,65,'Observer / verifier','I ADC + compare + valid')
block(760,5400,450,65,'Local correction / analog controls','I/Q offset trims · clock bank · frontend settings')
wire([(985,5275),(985,5400)])
wire([(760,5432),(635,5432)])
wire([(520,5400),(520,5275)])
wire([(405,5432),(315,5432)])
wire([(85,5432),(70,5432),(70,5100),(385,5100),(385,5085)])
label(90,5510,'*Memory requests from SPI / RX capture / TX playback are arbitrated.',16,anchor='start')
label(90,5540,'Capture: RF / wired RX taps → memory. Playback: MEM_TX_RF / WIRE.',16,anchor='start')

panel(1300,4925,1245,635,'RF CLOCK ACQUISITION — COUNT, COARSE TUNE, FINE LOOP','#f8f3fc')
block(1330,5035,180,65,'REF buffer','REF_IN')
block(1600,5035,210,65,'Window / timer','REF ticks')
block(1910,5035,245,65,'Coarse controller','search / guard / qualify')
block(2265,5035,240,65,'VCO bank latch','coarse frequency')
for a,b in [(1510,1600),(1810,1910),(2155,2265)]:wire([(a,5067),(b,5067)])
block(1330,5230,230,65,'Snapshot CDC','coherent count / valid')
block(1640,5230,230,65,'Prescale + counter','VCO → ÷16 → count')
block(1960,5230,195,65,'VCO','phase continuous')
wire([(1960,5262),(1870,5262)]);wire([(1640,5262),(1560,5262)])
wire([(1445,5230),(1445,5170),(2025,5170),(2025,5100)])
wire([(2385,5100),(2385,5205),(2057,5205),(2057,5230)])
wire([(1705,5100),(1705,5195),(1445,5195),(1445,5230)])
label(1510,5188,'Snapshot request',15)
block(1330,5410,195,65,'PFD / CP','fine phase error')
block(1640,5410,230,65,'R–C loop filter','continuous charge')
block(1960,5410,245,65,'÷N feedback','integer / fractional')
wire([(1525,5442),(1640,5442)]);wire([(1870,5442),(1915,5442),(1915,5305),(2057,5305),(2057,5295)])
wire([(1940,5262),(1940,5348),(2082,5348),(2082,5410)]);dot(1940,5262)
wire([(1960,5442),(1910,5442),(1910,5500),(1427,5500),(1427,5475)])
wire([(1340,5100),(1315,5100),(1315,5375),(1427,5375),(1427,5410)],clock=True)
wire([(2120,5100),(2205,5100),(2205,5320),(1550,5320),(1550,5360),(1460,5360),(1460,5410)],clock=True)
label(1800,5342,'Search: hold pump; qualified bank → enable fine PLL',15,color='#80549c')
label(1330,5540,'Initial acquisition candidate; live coarse retune / recenter circuitry remains open.',16,anchor='start')

label(55,5620,'LOCAL NET MAP — THESE ARE INTERNAL CONNECTIONS, NOT ADDITIONAL EXTERNAL TERMINALS',24,True,'start')
rows=[
('LO-I / LO-Q','RF VCO → quadrature buffers → separate RX-I, RX-Q, TX-I, TX-Q mixer LO ports.'),
('CLK / RESET','Reference-derived timing → conversion step, ADC sample, DAC update, host launch; RESET_N / fault → local reset release.'),
('Analog control','Per-island latches → gain cells, filter switches, offset actuators, diagnostic selectors, termination, driver bias / tap weights.'),
('Analog returns','Buffered amplitude / idle / local comparator → monitor selection → I ADC or calibration comparator → valid / result status.'),
('VDD/VSS_CORE','Core logic, FIFO / memory, configuration / calibration and pad pre-drivers; dedicated feed and return.'),
('VDD/VSS_HOST_A / B','A: data[4:0], SPI/reset pads. B: data[9:5], host clocks. Separate output-driver feeds / returns.'),
('VDD/VSS_WIRE_A / B','Two wired analog feed / return pairs; local RX/TX allocation and rail continuity require physical closure.'),
('VDD/VSS_RF / PLL','RF: RF frontends, baseband and converters. PLL: clock / master references. Local bias / reference buffers isolate loads.')]
for i,(name,detail) in enumerate(rows):
    y=5675+i*39
    label(75,y,name,17,True,'start');label(460,y,detail,17,anchor='start')
label(55,6035,'Wiring is architectural intent: CDC primitives, transistor-level switching, exact widths / values and physical supply isolation are not yet closed.',18,anchor='start')


# Circuit wiring expansions. Differential conductors are explicitly separated;
# named edge ports join the overview, not new package pins.
label(55,6130,'LOCAL CIRCUIT WIRING / DIFFERENTIAL NETS AND FEEDBACK',29,True,'start')
label(55,6170,'Repeat each I/Q sheet twice. P and N are separate conductors; identical net names join sheets. Proposed implementation interfaces.',18,anchor='start')
def pair(x1,x2,y,name=None):
    wire([(x1,y-10),(x2,y-10)])
    wire([(x1,y+10),(x2,y+10)])
    if name: label((x1+x2)/2,y-24,name,14,True)
def named(x,y,name,clock=False,color=None):
    global WIRE_COLOR
    old=WIRE_COLOR; WIRE_COLOR=color
    wire([(x,y),(x,y+32)],clock=clock)
    label(x,y-10,name,14,True,color=color or ('#80549c' if clock else '#172a3a'))
    WIRE_COLOR=old

def chain_panel(y,title,names,nets):
    panel(55,y,2490,420,title,'#f1f8f5')
    # Wide channels between symbols keep the two conductors and labels distinct.
    xs=[210,690,1170,1650,2130]
    for x,(name,sub) in zip(xs,names):block(x,y+140,240,80,name,sub)
    for i,net in enumerate(nets):pair(xs[i]+240,xs[i+1],y+180,net)
    if y==6670:
        wire([(80,y+180),(210,y+180)]);label(140,y+155,'TX_CODE',14,True)
    else: pair(80,210,y+180,'IN_P/N')
    pair(2370,2520,y+180,'OUT_P/N')
    return xs

xs=chain_panel(6210,'RX BASEBAND × I/Q — MIXER OUTPUT TO THE ADC INPUT',[
    ('Mixer load / TIA','differential current → voltage'),('PGA / summer','gain + offset injection'),
    ('Tunable LPF','two biquads + one real pole'),('Source select / buffer','RF or diagnostic; I only'),
    ('Track / hold + CDAC','P/N sampling switches')],['BB_P/N','GAIN_P/N','FILT_P/N','ADC_IN_P/N'])
for x,net in zip(xs,['IBIAS_RX / VCM','RX_GAIN / OFFSET','RX_RC / GM_CODE','DIAG_SELECT','SAMPLE / HOLD']):
    named(x+120,6318,net,clock=x == 2130)
# Common-mode loop is distinct from differential offset correction.
block(730,6510,290,60,'Offset integrator / trim','slow differential feedback')
wire([(1470,6380),(1470,6485),(875,6485),(875,6510)]);dot(1470,6380)
wire([(1490,6400),(1490,6500),(925,6500),(925,6510)]);dot(1490,6400)
wire([(730,6540),(650,6540),(650,6450),(760,6450),(760,6430)])
label(1110,6475,'sense FILT_P − FILT_N',14)
block(1640,6510,340,60,'Common-mode sensing / error','(OUT_P + OUT_N)/2 vs VCM')
wire([(2040,6380),(2040,6530),(1980,6530)]);dot(2040,6380)
wire([(2060,6400),(2060,6550),(1980,6550)]);dot(2060,6400)
wire([(1640,6540),(1590,6540),(1590,6465),(1770,6465),(1770,6430)])
label(90,6598,'Local bias: TIA, PGA, filter and buffer each receive IBIAS_RX and VCM. Each active differential stage needs its own common-mode control.',16,anchor='start')

xs=chain_panel(6670,'TX BASEBAND × I/Q — HELD DAC CODE THROUGH RECONSTRUCTION TO RF',[
    ('DAC cells + I/V','registered code; VREF / IBIAS'),('Reconstruction section 1','differential biquad'),
    ('Reconstruction section 2','differential biquad'),('Output buffer / gain','finite bandwidth / loading'),
    ('Quadrature mixer','I or Q LO; current output')],['DAC_P/N','SEC1_P/N','SEC2_P/N','TX_BB_P/N'])
for x,net in zip(xs,['DAC_UPDATE','TX_RC1 / Q1','TX_RC2 / Q2','TX_GAIN / VCM','TX_LO_I or Q']):
    named(x+120,6778,net,clock=x in (210,2130))
for x in (690,1170):
    block(x,6970,240,52,'R/C feedback network','section coefficients')
    wire([(x+280,6840),(x+280,6985),(x+240,6985)]);dot(x+280,6840)
    wire([(x+300,6860),(x+300,7005),(x+240,7005)]);dot(x+300,6860)
    wire([(x,6996),(x-35,6996),(x-35,6905),(x+45,6905),(x+45,6890)])
block(1680,6970,670,52,'I mixer + Q mixer → differential current sum → RF driver','RF_TX_P/N; driver enable / bias / amplitude sense')
label(90,7058,'Two-biquad reconstruction is a mathematical candidate. Realization, tuning range, op-amp bandwidth, Q, noise and headroom remain open.',16,anchor='start')

panel(55,7130,2490,540,'WIRED LANE — EXPLICIT CLOCK, DATA, DETECTION AND LOOPBACK PORTS','#f2f5fc')
for x,title,sub in [(210,'Termination / CTLE','WIRE_RX_P/N'),(690,'Data + edge samplers','independent decision outputs'),(1170,'Deserializer / align','parallel words + valid'),(1650,'RX async FIFO','CLK_RX → host clock'),(2130,'Host RX scheduler','D2H data / clock')]:
    block(x,7250,240,80,title,sub)
pair(80,210,7290,'RX_P/N');pair(450,690,7290,'EQ_P/N')
for a,b,name in [(930,1010,'BITS'),(1410,1650,'RX_WORD / VALID'),(1890,2130,'WORD / VALID')]:
    wire([(a,7290),(b,7290)]);label((a+b)/2,7270,name,14,True)
block(690,7430,240,65,'Phase detector','edge + data decisions')
block(1170,7430,240,65,'CDR loop / phase control','loop state → phase actuator')
wire([(840,7330),(840,7430)])
wire([(930,7462),(1170,7462)])
wire([(1290,7495),(1290,7540),(620,7540),(620,7220),(810,7220),(810,7250)],clock=True)
label(965,7527,'CLK_RX / SAMPLE_PHASE',15,color='#80549c')
wire([(1290,7540),(1530,7540),(1530,7370),(1290,7370),(1290,7330)],clock=True);dot(1290,7540)
block(210,7430,240,65,'RX idle detector','tap EQ_P/N; separate buffer')
wire([(500,7280),(500,7390),(310,7390),(310,7430)]);dot(500,7280)
wire([(520,7300),(520,7410),(350,7410),(350,7430)]);dot(520,7300)
wire([(330,7495),(330,7580),(450,7580)]);label(560,7585,'RX_IDLE → status',14)
wire([(1530,7370),(1700,7370),(1700,7330)],clock=True);dot(1530,7370)
label(1765,7360,'FIFO write clock',14,color='#80549c')
block(1650,7430,240,65,'Local loopback selector','normal RX / TX data; quiet only')
block(2130,7430,240,65,'TX sense / detect','output load / idle state')
block(1010,7260,100,60,'RX mux')
wire([(1110,7290),(1170,7290)])
wire([(1770,7430),(1770,7385),(1060,7385),(1060,7320)])
named(1770,7368,'SERIAL_TX / LB_SELECT')
named(2250,7398,'WIRE_TX_P/N / DET_EN')
label(90,7625,'TX: word FIFO → serializer (CLK_TX) → main / delayed current taps → differential output driver → WIRE_TX_P/N.',16,anchor='start')
label(90,7650,'TX electrical idle disables output drive; receiver detection uses its own stimulus and sense path. CLK_TX and recovered CLK_RX are independent.',16,anchor='start')

panel(55,7710,2490,650,'LOCAL SERVICES — INDIVIDUAL CONTROL AND RETURN CONNECTIONS','#fbf8ed')
label(95,7770,'REGISTER / CLOCK / REFERENCE SOURCE',18,True,anchor='start')
label(1030,7770,'NAMED NET (INTERNAL)',18,True,anchor='start')
label(1770,7770,'DESTINATION / RETURN',18,True,anchor='start')
services=[
 ('RX configuration latches','RX_GAIN, RX_RC, OFFSET_I/Q','PGA / LPF / offset actuators','#386991'),
 ('TX configuration latches','TX_RC1/2, TX_GAIN, TX_ENABLE','Reconstruction / mixer / RF driver','#386991'),
 ('Wired configuration latches','TERM, EQ, TAP0/1, IDLE, DET_EN','Termination / CTLE / TX driver / detect','#386991'),
 ('RF quadrature LO buffers','LO_I_RX, LO_Q_RX, LO_I_TX, LO_Q_TX','Four distinct mixer LO loads','#80549c'),
 ('Sample / conversion sequencer','ADC_SAMPLE, SAR_STEP, DAC_UPDATE','Both ADCs / paired DAC update latches','#80549c'),
 ('Reference buffers + local reservoirs','VREF_P, VREF_N, VCM; separate conductors','ADC CDACs / DACs / common-mode loops','#b47a20'),
 ('Master bias + local mirrors','IBIAS_RX, IBIAS_TX, IBIAS_WIRE, IBIAS_PLL','Local bias input of each active circuit','#b47a20'),
 ('Reset / qualification controller','RESET_LOCAL, ISOLATE, RUN_ENABLE','Clock gates / FIFO epochs / safe outputs','#386991'),
 ('Analog monitor input buffers','RF amplitude, TX load, bias sense (selected)','Monitor mux → I ADC or comparator','#233e50'),
 ('Local status / measurement latches','LOCK, IDLE, DETECT, ADC_VALID, FAULT','Status CDC → SPI and host event formatter','#386991'),
 ('Domain supply / return pads','VDD_DOMAIN, VSS_DOMAIN (separate nets)','Decoupling → every local circuit supply','#94504d'),
]
for i,(source,net,dest,color) in enumerate(services):
    yy=7815+i*44
    label(95,yy,source,16,anchor='start')
    WIRE_COLOR=color;wire([(590,yy-5),(995,yy-5)]);WIRE_COLOR=None
    label(1020,yy,net,15,anchor='start',color=color)
    WIRE_COLOR=color;wire([(1670,yy-5),(1750,yy-5)]);WIRE_COLOR=None
    label(1770,yy,dest,15,anchor='start')
label(95,8335,'Names with commas list separate nets, not shorted conductors. Buses retain separate bits; clocks require local buffering; supply returns are not signal returns.',16,anchor='start')
label(55,8400,'Full block-level connection intent. Device sizing, analog switch topology, RC values and extracted wiring remain subsequent schematic/layout work.',18,anchor='start')


# Complete the RF output circuit and its observation branch explicitly.
label(55,8500,'RF OUTPUT / PAIRED UPDATES / POWER AND BIAS WIRING',29,True,'start')
label(55,8538,'Connection detail supplements the placement overview. Ports repeat existing internal nets; no additional package terminals.',18,anchor='start')
panel(55,8580,2490,680,'RF CURRENT SUM → DRIVER → PADS; SEPARATE LO AND MONITOR CONNECTIONS','#f1f8f5')
for y,ch in [(8720,'I'),(9010,'Q')]:
    block(130,y,245,80,f'{ch} reconstruction output','differential voltage')
    block(550,y,230,80,f'{ch} mixer','voltage → RF current')
    pair(375,550,y+40,f'TX_{ch}_P/N')
    named(665,y-32,f'LO_{ch}_TX',clock=True)
    named(260,y-32,f'TX_{ch}_GAIN / VCM')
# Separate P/N current summing junctions; crossed wires without dots do not join.
for y in (8760,9050):
    wire([(780,y-10),(950,y-10),(950,8880)],False)
    wire([(780,y+10),(995,y+10),(995,8900)],False)
dot(950,8880); dot(995,8900)
label(900,8830,'ΣP',18,True);label(1030,8960,'ΣN',18,True)
block(1140,8850,250,80,'Differential RF driver','current gain / output bias')
wire([(950,8880),(1140,8880)]);wire([(995,8900),(1140,8900)])
block(1580,8850,260,80,'Switches + protection','expanded isolation sheet below')
pair(1390,1580,8890,'DRV_P/N')
block(2200,8850,290,80,'RF_TX_P / RF_TX_N','existing 2 edge terminals')
pair(1840,2200,8890,'PAD_P/N')
named(1250,8818,'TX_ENABLE / IBIAS_TX')
block(1550,9080,300,75,'High-impedance tap','differential sense / isolation')
wire([(1450,8880),(1450,9020),(1940,9020),(1940,9100),(1850,9100)]);dot(1450,8880)
wire([(1490,8900),(1490,9045),(1980,9045),(1980,9135),(1850,9135)]);dot(1490,8900)
block(1110,9080,270,75,'Envelope / power detector','rectify → RC integration')
wire([(1550,9117),(1380,9117)])
block(580,9150,350,65,'Buffered monitor selector','power / bias / local analog')
wire([(1110,9117),(1020,9117),(1020,9182),(930,9182)])
wire([(580,9182),(130,9182)]);label(355,9170,'MON_ANALOG → I ADC diagnostic input',15)
label(1110,9210,'Pre-switch tap; output / dummy switches are expanded on the isolation sheet below.',16,anchor='start')

panel(55,9300,2490,475,'PAIRED DAC COMMIT — INDIVIDUAL DATA, SHARED TIMING, RETURN ACKNOWLEDGEMENT','#edf4fb')
for y,ch in [(9400,'I'),(9610,'Q')]:
    block(100,y,250,70,f'TX {ch} queue','code + epoch + valid')
    block(560,y,250,70,f'{ch} shadow register','hold pending code')
    block(1120,y,250,70,f'{ch} active register','hold until shared update')
    block(1640,y,260,70,f'{ch} DAC cells','analog output to LPF')
    for a,b in [(350,560),(810,1120),(1370,1640)]:wire([(a,y+35),(b,y+35)])
block(2110,9500,350,80,'Pair / epoch / readiness check','both valid + clock qualified + run')
wire([(685,9400),(685,9365),(2285,9365),(2285,9500)])
wire([(685,9680),(685,9720),(2285,9720),(2285,9580)])
wire([(2110,9540),(1000,9540)],False,True)
wire([(1000,9540),(1000,9385),(1245,9385),(1245,9400)],clock=True)
wire([(1000,9540),(1000,9590),(1245,9590),(1245,9610)],clock=True);dot(1000,9540)
label(1470,9528,'One DAC_UPDATE → both active latches',16,color='#80549c')
wire([(2110,9560),(430,9560)],False)
for yy in (9470,9680):wire([(430,9560),(430,yy+15),(225,yy+15),(225,yy)])
dot(430,9560);label(665,9550,'PAIR_CONSUMED → advance both queues',15)
label(100,9750,'Invalid epoch / missing partner inhibits commit; fault handling selects the declared safe output state.',16,anchor='start')

panel(55,9810,2490,480,'LOCAL POWER AND BIAS — REPEAT PER DOMAIN; SUPPLY AND RETURN ARE DISTINCT WIRES','#fbf8ed')
block(130,9940,250,80,'VDD_DOMAIN pad','one of 7 supply terminals')
block(130,10140,250,80,'VSS_DOMAIN pad','paired return terminal')
block(1920,10020,490,80,'Local circuit supply ports','VDD top / VSS bottom; repeated fanout')
WIRE_COLOR='#94504d'
wire([(380,9980),(2165,9980),(2165,10020)],False)
wire([(380,10180),(2165,10180),(2165,10100)],False)
# Explicit decoupling capacitor between supply and return, not a signal ground.
wire([(760,9980),(760,10065)],False)
wire([(730,10065),(790,10065)],False);wire([(730,10085),(790,10085)],False)
wire([(760,10085),(760,10180)],False);dot(760,9980);dot(760,10180)
WIRE_COLOR=None
label(635,10080,'Cdec',17,True)
block(1020,10030,350,70,'Local bias mirror / buffer','master IREF → local IBIAS')
label(1195,10014,'IREF_DOMAIN',14,True,color='#b47a20')
WIRE_COLOR='#b47a20'
wire([(1195,10017),(1195,10030)])
WIRE_COLOR=None
WIRE_COLOR='#b47a20'
wire([(1370,10065),(1920,10065)])
WIRE_COLOR=None
label(1630,10050,'IBIAS_DOMAIN',16,color='#b47a20')
wire([(1320,9980),(1320,10030)],False);dot(1320,9980)
wire([(1320,10100),(1320,10180)],False);dot(1320,10180)
label(100,10255,'Repeat for CORE, HOST_A, HOST_B, WIRE_A, WIRE_B, RF and PLL. No implicit connection between separately named VDD rails.',16,anchor='start')
label(55,10340,'Circuit-block connectivity proposal; device topology, component values, resource conflicts and electrical verification remain schematic work.',18,anchor='start')


# Expanded connectivity for the switched-output/shared-converter candidate.
# Named ports refer to existing sheets; they never create package pins.
label(55,10425,'OUTPUT ISOLATION / SHARED ADC — CONNECTED CANDIDATE WIRING',29,True,'start')
label(55,10465,'Expands the RF driver-to-pad path above. Switches, dummy load and readout buffer remain circuit candidates.',18,anchor='start')
panel(55,10500,2490,710,'RF OUTPUT: DISTINCT P/N SWITCHES, INTERNAL DUMMY LOAD AND PRE-SWITCH OBSERVATION','#f1f8f5')
block(120,10670,270,100,'RF differential driver','from I/Q current sum')
block(780,10670,260,100,'Output switch pair','OUT_EN; finite off C')
block(1450,10670,260,100,'Protection / bias','ESD + pad capacitance')
block(2160,10670,300,100,'RF_TX_P / RF_TX_N','2 existing package pads')
for a,b,net in [(390,780,'DRV_P / DRV_N'),(1040,1450,'SW_P / SW_N'),(1710,2160,'PAD_P / PAD_N')]:
    pair(a,b,10720,net)
block(460,10865,260,90,'Dummy switch pair','DUMMY_EN')
block(850,10865,300,90,'Differential dummy load','R / C; common-mode bias')
wire([(490,10710),(490,10865)]);dot(490,10710)
wire([(535,10730),(535,10865)]);dot(535,10730)
pair(720,850,10910,'DUM_P/N')
block(1440,10865,280,90,'Isolated differential tap','finite R / C input loading')
wire([(630,10710),(630,10805),(1530,10805),(1530,10865)]);dot(630,10710)
wire([(675,10730),(675,10835),(1620,10835),(1620,10865)]);dot(675,10730)
block(2040,10865,400,90,'Power detector + integration','square-law candidate; RC state')
wire([(1720,10910),(2040,10910)])
wire([(2240,10955),(2240,11065),(2460,11065)])
label(2240,11100,'DET_POWER → readout sheet below',16)
block(100,11020,570,90,'Quiet / run / calibration output sequencer','switch controls; preserve analog charge on stop')
WIRE_COLOR='#386991'
wire([(385,11020),(385,10830),(590,10830),(590,10865)])
wire([(180,11020),(180,10820),(80,10820),(80,10590),(910,10590),(910,10670)])
WIRE_COLOR=None
label(1090,10595,'OUT_EN → both P/N devices',16,color='#386991',anchor='start')
label(470,10850,'DUMMY_EN',14,color='#386991',anchor='start')
label(750,11045,'Run: output on / dummy off. Quiet calibration: output off / dummy on.',18,anchor='start')
label(750,11080,'Transition ordering, feedthrough, dummy matching and stored-charge settling require verification.',17,anchor='start')
label(95,11170,'Differential lines remain distinct. Dummy termination is across DUM_P/N with a separate common-mode bias; it is not a short to VSS.',17,anchor='start')

panel(55,11250,2490,835,'DETECTOR READOUT: SHARED I ADC, RESOURCE OWNERSHIP AND SEPARATE RESULT ROUTING','#fbf8ed')
block(100,11405,255,80,'Detector RC output','DET_POWER; continuous state')
amp(515,11445,'A','Readout buffer')
wire([(355,11445),(465,11445)])
block(740,11405,300,80,'I-channel source mux','RX-I / detector / slow diag')
wire([(565,11445),(740,11445)])
block(1220,11405,290,80,'I track / hold + CDAC','same I converter as RF RX')
wire([(1040,11445),(1220,11445)])
block(1690,11405,290,80,'Comparator + SAR','bit trials → result latch')
wire([(1510,11445),(1690,11445)])
block(2180,11405,300,80,'Result / owner demux','epoch + valid + overflow')
wire([(1980,11445),(2180,11445)])
label(795,11320,'RX-I_P/N',16,True)
label(975,11320,'DIAG_OTHER',16,True)
wire([(795,11335),(795,11405)])
wire([(975,11335),(975,11405)])
label(1335,11305,'VREF_P / VREF_N / VCM',16,True,color='#b47a20')
WIRE_COLOR='#b47a20'
wire([(1300,11320),(1300,11405)])
wire([(1365,11320),(1365,11405)])
wire([(1430,11320),(1430,11405)])
WIRE_COLOR=None
wire([(1800,11485),(1800,11545),(1365,11545),(1365,11485)])
label(1570,11532,'SAR trial code → CDAC switches',16)
block(100,11710,370,85,'Calibration / quiet controller','request I ADC; wait grant / settle')
block(660,11710,380,85,'ADC ownership + mux sequencer','owner / select / settle / sample')
block(1220,11710,380,85,'Sample / conversion timing','ADC_SAMPLE / SAR_STEP / reset')
block(1800,11710,360,85,'Calibration result latch','power + epoch + valid + clip')
wire([(470,11735),(660,11735)])
wire([(660,11770),(470,11770)])
label(560,11720,'REQUEST',14,True)
label(560,11800,'GRANT / BUSY',14,True)
WIRE_COLOR='#386991'
wire([(850,11710),(850,11585),(890,11585),(890,11485)])
wire([(1040,11750),(1220,11750)])
wire([(1040,11785),(1100,11785),(1100,11610),(2110,11610),(2110,11495),(2330,11495),(2330,11485)])
WIRE_COLOR=None
label(1020,11575,'MUX_SELECT',15,color='#386991')
label(2060,11595,'OWNER / EPOCH',15,color='#386991')
wire([(1340,11710),(1340,11655),(1190,11655),(1190,11360),(1250,11360),(1250,11405)],clock=True)
wire([(1480,11710),(1480,11680),(1630,11680),(1630,11360),(1835,11360),(1835,11405)],clock=True)
label(1830,11665,'SAMPLE / STEP: separate nets',15,color='#80549c')
wire([(2410,11485),(2410,11750),(2160,11750)])
wire([(2330,11405),(2330,11300),(2490,11300)])
label(2220,11290,'RX owner → RF RX queue',15)
wire([(1980,11795),(1980,11900),(285,11900),(285,11795)])
label(1130,11888,'RESULT → next trial / verify / commit; completion releases ADC ownership',17)
label(95,11955,'Single-ended detector-to-differential ADC mapping needs gain / common-mode conditioning in the readout buffer. Q ADC remains separate.',17,anchor='start')
label(95,11995,'Sample demand loads the existing reference network. Mux resistance, charge injection, buffer settling and ADC kickback are not ideal wires.',17,anchor='start')
label(95,12035,'Shared ADC blocks concurrent I-channel RX during calibration. Abort discards pending results; continuous detector and network charge remain.',17,anchor='start')
label(55,12135,'Architectural connection intent, not a verified electrical netlist. All named buses represent separate conductors; crossings without junction dots do not connect.',17,anchor='start')


# Service nets have actual branching junctions and individual receiving ports.
label(55,12235,'CLOCK / REFERENCE / BIAS DISTRIBUTION — EXPLICIT RECEIVING PORTS',29,True,'start')
label(55,12275,'Internal sheet connections use identical net names. Separate output routes preserve independent clocks, bias nets and reference conductors.',18,anchor='start')
def fanout_sheet(y,title,source,conditioning,net,receivers,color):
    global WIRE_COLOR
    panel(55,y,2490,330,title,'#fafbfd')
    block(100,y+130,330,80,source[0],source[1])
    block(590,y+130,360,80,conditioning[0],conditioning[1])
    WIRE_COLOR=color
    wire([(430,y+170),(590,y+170)])
    # Separate output ports and routes: no shared electrical junction.
    # Expand slash-labelled differential pairs on the local circuit sheets.
    label(1030,y+77,net,16,True,color=color)
    for i,(dy,(destination,port)) in enumerate(zip((105,180,255),receivers)):
        exit_y=y+145+25*i
        bend=1010+35*i
        wire([(950,exit_y),(bend,exit_y),(bend,y+dy),(1570,y+dy)])
        label(1310,y+dy-12,port,15,color=color)
        block(1570,y+dy-25,885,50,destination)
    WIRE_COLOR=None
fanout_sheet(12315,'RF LO: ISOLATE MIXER LOADS FROM THE SYNTHESIZER',
 ('RF VCO / phase generator','from RF synthesizer sheet'),('Four local LO drivers','I-RX / Q-RX / I-TX / Q-TX'),
 'LO distribution', [('RX I and Q switching mixers','LO_I_RX / LO_Q_RX'),('TX I and Q switching mixers','LO_I_TX / LO_Q_TX'),('Feedback divider / frequency counter','VCO_SENSE (isolated branch)')], '#80549c')
label(100,12620,'Each slash-separated name is a separate clock net: this fanout denotes connectivity, not shorted I/Q phases.',16,anchor='start')
fanout_sheet(12685,'CONVERTER TIMING: DISTINCT SAMPLE, DECISION AND COMMIT EVENTS',
 ('Qualified sample clock','reference-derived timing service'),('Divider / event sequencer','local gating; safe reset release'),
 'timing bus', [('I and Q track-and-hold switches','ADC_SAMPLE_I / ADC_SAMPLE_Q'),('I and Q SAR state machines','SAR_STEP_I / SAR_STEP_Q'),('I and Q active DAC code latches','DAC_UPDATE (shared pair commit)')], '#80549c')
fanout_sheet(13055,'CONVERTER REFERENCE: BUFFERED RESERVOIR AND SWITCHED LOADS',
 ('Master reference','VREF_SET / analog return'),('Reference buffer + reservoir','feedback senses loaded VREF'),
 'VREF_P / VREF_N', [('I and Q SAR capacitor-array reference switches','VREF_P / VREF_N → each CDAC'),('I and Q DAC reference / current-setting cells','VREF_P / VREF_N → each DAC'),('Buffered reference diagnostic input','VREF_SENSE → DIAG_OTHER mux')], '#b47a20')
# Explicit sense return, separate from output fanout.
wire([(1000,13225),(1000,13340),(770,13340),(770,13265)])
dot(1000,13225);label(800,13370,'Kelvin sense intent; return is VREF_N',15)
fanout_sheet(13425,'BIAS AND COMMON MODE: SEPARATE LOCAL MIRRORS / BUFFERS',
 ('Bias startup + master IREF','trim / startup feedback'),('Local mirrors and VCM buffers','separate RF / BB / wired / PLL loads'),
 'bias bundle', [('LNA, mixers, RF output driver and LO buffers','IBIAS_RX / MIX / TX / LO'),('PGA, filters, ADC input buffers and CMFB amplifiers','IBIAS_BB / VCM_RX / VCM_TX'),('Wired CTLE, slicers, line driver, VCO and charge pumps','IBIAS_WIRE / VCO / CP')], '#b47a20')
panel(55,13795,2490,610,'RESET / QUALIFICATION / FAULT RETURN — CONTROL WIRES CLOSE THE LOOP','#edf4fb')
block(100,13905,360,80,'RESET_N + SPI requests','external reset / run / abort / mode')
block(655,13905,430,80,'Mode and resource sequencer','clock ready + owner + epoch + run')
wire([(460,13945),(655,13945)])
for yy,title,net in [(13915,'Local reset synchronizers → all digital domains','RESET_REQ'),(14055,'RF / wired output and dummy-switch controls','OUT_EN / IDLE / DUMMY_EN'),(14195,'ADC mux, DAC commit and queue controls','OWNER / SAMPLE_EN / COMMIT_EN')]:
    block(1730,yy-30,710,60,title)
    wire([(1085,13945),(1190,13945),(1190,yy),(1730,yy)])
    label(1460,yy-12,net,16,color='#386991')
dot(1190,13945)
block(655,14265,650,80,'Sticky status + synchronized fault inputs','lock / reference loss / overflow / calibration done')
wire([(980,14265),(980,13985)])
label(1050,14130,'QUALIFIED',15,anchor='start')
block(1730,14300,710,60,'Clock monitors / queues / calibration engine')
wire([(1730,14330),(1305,14330)])
wire([(655,14305),(280,14305),(280,13985)])
label(380,14288,'SPI_STATUS / readback',16)
label(95,14390,'Control bundles contain independent signals. Reset release is synchronized per destination clock; analog startup remains a separate circuit obligation.',16,anchor='start')
label(55,14460,'These connections complete service routing at circuit-block granularity. Component pins, values and parasitics require the subsequent electrical schematic.',17,anchor='start')


# Package boundary detail: separate electrical conductors and receiving pins.
label(55,14545,'PACKAGE-TO-CIRCUIT WIRING / DOMAIN CROSSINGS',29,True,'start')
label(55,14585,'Same 50 terminals as the overview. Named destinations join existing sheets; no additional external test or bias pins.',18,anchor='start')
panel(55,14620,2490,810,'ANALOG TERMINALS — EACH P AND N CONDUCTOR REMAINS INDEPENDENT','#f1f8f5')
for row,(name,dest,domain,tx) in enumerate([
 ('RF_RX','LNA differential input','RF',False),
 ('RF_TX','Output-isolation switches','RF',True),
 ('WIRE_RX','Termination / CTLE input','WIRE',False),
 ('WIRE_TX','Segmented line driver','WIRE',True)]):
    y=14720+row*175
    block(100,y,270,105,name+'_P / _N','two perimeter terminals')
    block(620,y,340,105,'Pad protection cells','separate P and N signal ports')
    block(1320,y,440,105,dest,'P input/output above N')
    for offset,ch in [(30,'P'),(75,'N')]:
        pts=[(370,y+offset),(620,y+offset)]
        wire(pts[::-1] if tx else pts)
        pts=[(960,y+offset),(1320,y+offset)]
        wire(pts[::-1] if tx else pts)
        label(1110,y+offset-9,name+'_'+ch,15)
    block(2040,y,400,105,domain+' pad return / clamp','domain-qualified ESD network')
    wire([(790,y+105),(790,y+135),(1950,y+135),(1950,y+53),(2040,y+53)],False)
    label(1470,y+126,'ESD return path; not a signal termination',14)
label(100,15400,'RF matching / baluns and wired channel coupling are board-side, mode-dependent networks. ESD topology and loading remain to be selected.',16,anchor='start')
panel(55,15465,2490,745,'FAST HOST PORT — TEN REPEATED DATA WIRES AND A SEPARATE FORWARDED CLOCK','#edf4fb')
for y,name,tx in [(15565,'H2D',False),(15865,'D2H',True)]:
    titles=([('Input pad receivers','10 separate D[i] pins'),('Input-domain boundary','level conversion if required'),('DDR capture registers','D inputs; Q → H2D deframer')]
            if not tx else [('Output pad drivers','10 separate D[i] pins'),('Output-domain boundary','isolation / level conversion'),('DDR launch registers','D ← D2H formatter; Q outputs')])
    block(90,y,270,90,name+'_D[9:0]','10 perimeter terminals')
    for x,(title,sub) in zip([555,1110,1830],titles): block(x,y,430,90,title,sub)
    for a,b in [(360,555),(985,1110),(1540,1830)]:
        wire([(b,y+45),(a,y+45)] if tx else [(a,y+45),(b,y+45)])
    label(1650,y+30,'D[i], i = 0…9',15)
    block(90,y+150,270,70,name+'_CLK','one perimeter terminal')
    block(555,y+150,430,70,'Clock pad '+('driver' if tx else 'receiver'),'dedicated clock conductor')
    block(1110,y+150,430,70,'Clock '+('forwarding' if tx else 'conditioning'),'qualified phase / local clock tree')
    for a,b in [(360,555),(985,1110)]:
        wire([(b,y+185),(a,y+185)] if tx else [(a,y+185),(b,y+185)],clock=True)
    if tx:
        label(2350,y+185,'CLK_D2H',16,color='#80549c')
        wire([(2280,y+185),(1540,y+185)],clock=True)
        dot(2070,y+185);wire([(2070,y+185),(2070,y+90)],clock=True)
    else:
        wire([(1540,y+185),(2070,y+185),(2070,y+90)],clock=True)
    label(1890,y+240,('Launch Q → pads; same source forwards clock' if tx else 'Captured words → asynchronous FIFO → core'),16)
label(100,16180,'Input/output domain boundary blocks are conditional on chosen voltages. IO supplies feed pad circuits; CORE feeds transport logic. No direct clock-domain short.',16,anchor='start')
panel(55,16245,2490,850,'CONTROL / REFERENCE TERMINALS — INDIVIDUAL SIGNAL ROUTES','#fafbfd')
for i,(pinname,condition,destination,reverse) in enumerate([
 ('HOST_CS_N','Input pad / domain boundary','SPI chip-select input',False),
 ('HOST_SCLK','Clock input pad / domain boundary','SPI shift-register clock',False),
 ('HOST_MOSI','Input pad / domain boundary','SPI shift-register data input',False),
 ('HOST_MISO','Tristate output pad / domain boundary','SPI readback shift-register Q',True),
 ('RESET_N','Input pad / reset qualification','Async assert → per-domain sync release',False),
 ('REF_IN','Qualified reference input buffer','RF PLL / wired PLL / timing reference',False)]):
    y=16335+i*110
    block(90,y,290,65,pinname,'one perimeter terminal')
    block(665,y,590,65,condition)
    block(1670,y,790,65,destination)
    for a,b in [(380,665),(1255,1670)]:
        wire([(b,y+32),(a,y+32)] if reverse else [(a,y+32),(b,y+32)],clock=pinname in ('HOST_SCLK','REF_IN'))
# MISO enable is a distinct control conductor, not the output data net.
wire([(1600,16615),(1600,16645),(940,16645),(940,16665)])
label(1600,16605,'SPI_SELECTED',14)
label(1190,16635,'MISO_OE (inactive: high impedance)',15)
label(100,17035,'SPI register requests / readback cross into CORE through explicit handshake mailboxes (see control sheet); SCLK is not a core clock.',17,anchor='start')
label(100,17070,'Seven supply/return pairs connect to the domain distribution sheet. Board decoupling and on-die reservoirs return to their corresponding VSS.',17,anchor='start')
label(55,17150,'Connection intent only: pad-cell selection, level-shifter requirements, ESD clamps, electrical values and physical routing remain unqualified.',18,anchor='start')


# Electrical loop detail: preserve distinct pump, storage and tuning nodes.
label(55,17250,'PASSIVE NETWORKS / LOCAL ANALOG FEEDBACK',29,True,'start')
label(55,17290,'Named ports join earlier sheets. Circuit candidates below expand boxes; values and topology selection remain open.',18,anchor='start')
def resistor_h(x,y,name):
    wire([(x-65,y),(x-35,y)],False)
    rect(x-35,y-12,70,24)
    wire([(x+35,y),(x+65,y)],False)
    label(x,y-25,name,17)
def capacitor_v(x,y,name):
    wire([(x,y),(x,y+36)],False)
    wire([(x-24,y+36),(x+24,y+36)],False)
    wire([(x-24,y+48),(x+24,y+48)],False)
    wire([(x,y+48),(x,y+90)],False)
    label(x+34,y+49,name,17,anchor='start')
panel(55,17325,2490,790,'WIRED PLL — PFD, PUMP, TWO-CAP FILTER AND INTEGER-EDGE FEEDBACK','#f8f3fc')
block(100,17445,220,70,'REF_BUFFER_OUT','reference clock')
block(430,17445,230,120,'PFD + reset','REF / FB → UP / DN')
wire([(320,17480),(430,17480)],clock=True)
block(815,17425,265,180,'Charge pump','source / sink current')
for yy,net in [(17470,'UP'),(17535,'DN')]:
    wire([(660,yy),(815,yy)])
    label(730,yy-10,net,16)
wire([(1080,17500),(1690,17500),(2040,17500)],False)
label(1330,17475,'VCP = VTUNE (two-cap candidate)',17)
dot(1200,17500);dot(1550,17500);dot(1900,17500)
capacitor_v(1200,17500,'Cf')
wire([(1200,17590),(1200,17765)],False)
wire([(1550,17500),(1550,17590)],False)
# Horizontal R into an independent slow storage node.
resistor_h(1690,17590,'R')
wire([(1550,17590),(1625,17590)],False)
wire([(1755,17590),(1840,17590)],False)
label(1840,17565,'VSLOW',16)
capacitor_v(1840,17590,'Cs')
wire([(1840,17680),(1840,17765)],False)
wire([(1110,17765),(1940,17765)],False)
dot(1200,17765);dot(1840,17765)
label(1500,17795,'VSS_PLL — capacitor returns',17)
block(2040,17450,360,100,'VCO tuning input','VTUNE + COARSE_CODE')
wire([(2220,17550),(2220,17865),(1840,17865)],clock=True)
block(1450,17830,390,70,'Integer-edge divider','N[k] from ratio / sequence state')
wire([(1450,17865),(520,17865),(520,17565)],clock=True)
label(1020,17845,'FB_CLK',17,color='#80549c')
block(790,17675,290,75,'Pump bias / enable','IBIAS_CP / CP_EN')
wire([(940,17675),(940,17605)])
label(100,18015,'RF and wired PLLs are separate instances with separate storage, VCO outputs and feedback nets.',18,anchor='start')
label(100,18055,'RF three-cap candidate: see expanded sheet below for R3, C3, centering shunts and acquisition controls.',17,anchor='start')
panel(55,18105,2490,1060,'LOCAL ANALOG TILE — BOUNDED INPUT SELECTION, WEIGHT, INTEGRATION AND OBSERVATION','#fbf8ed')
block(100,18290,350,100,'Buffered local sources','selected DAC / slow monitor')
block(610,18290,300,100,'Input selector','one-hot switches; finite load')
wire([(450,18320),(610,18320)]);wire([(450,18365),(610,18365)])
label(525,18305,'P',16);label(525,18395,'N',16)
block(1070,18290,320,100,'Differential gm cell','signed programmable weight')
wire([(910,18320),(1070,18320)]);wire([(910,18365),(1070,18365)])
block(1620,18275,350,130,'Integrator amplifier','SUM_P / SUM_N → OUT_P / N')
wire([(1390,18320),(1620,18320)]);wire([(1390,18365),(1620,18365)])
# Separate feedback branches, one per differential half.
for xx,yy,ch,outy,iny in [(1510,18220,'P',18320,18320),(1450,18485,'N',18365,18365)]:
    wire([(1970,outy),(2030 if ch=='P' else 2080,outy),(2030 if ch=='P' else 2080,yy),(1810,yy)],False)
    # Inline capacitor, with explicit reset-switch bypass in parallel.
    wire([(1810,yy),(1770,yy)],False)
    wire([(1770,yy-20),(1770,yy+20)],False)
    wire([(1758,yy-20),(1758,yy+20)],False)
    wire([(1758,yy),(xx,yy),(xx,iny),(1620,iny)],False)
    label(1855,yy-23,'C_INT_'+ch,16)
    dot(xx,iny);dot(2030 if ch=='P' else 2080,outy)
    by=yy-65 if ch=='P' else yy+65
    wire([(1660,yy),(1660,by),(1738,by)],False);dot(1660,yy)
    switch(1760,by)
    wire([(1782,by),(1920,by),(1920,yy)],False);dot(1920,yy)
    label(1770,by-24,'RESET_INT_'+ch,15)
block(2220,18290,260,100,'Output buffer','P / N → DIAG_MUX')
wire([(1970,18320),(2220,18320)]);wire([(1970,18365),(2220,18365)])
block(1620,18605,350,95,'Common-mode servo','sense OUT_P and OUT_N')
wire([(2030,18320),(2150,18320),(2150,18630),(1970,18630)])
wire([(2080,18365),(2110,18365),(2110,18675),(1970,18675)])
dot(2030,18320);dot(2080,18365)
wire([(1620,18650),(1570,18650),(1570,18430),(1795,18430),(1795,18405)])
label(1400,18630,'CMFB actuator',16)
block(100,18750,470,90,'Local configuration latches','SOURCE_SEL / SIGN / WEIGHT / RESET')
for x,y in [(760,18390),(1230,18390)]:
    wire([(570,18795),(x,18795),(x,y)])
    dot(x,18795)
label(965,18765,'Independent control nets (bundle)',16)
block(1620,18800,350,80,'VCM / IBIAS / VDD / VSS','separate service ports')
wire([(1795,18800),(1795,18700)])
label(100,18955,'Reset switches discharge each integration capacitor; the controller applies RESET_INT_P and RESET_INT_N together.',17,anchor='start')
label(100,18995,'Integrator outputs also feed the local comparator / sample path shown in the overview. The diagnostic mux is a bounded local route.',17,anchor='start')
label(100,19035,'Local selection and weight programming do not imply a global RF crossbar. Tile count, switch circuits and legal modes remain to be fixed.',17,anchor='start')
label(55,19220,'Lines show intended electrical connectivity; this is not yet a complete transistor netlist or an LVS-qualified schematic.',19,anchor='start')


# Candidate selected by isolated edge-driven screens: do not silently replace the
# separate wired PLL or imply that mathematical voltages are absolute rail levels.
label(55,19330,'RF PLL / THREE-STORAGE-NODE WIRING',29,True,'start')
label(55,19370,'Candidate circuit connectivity; isolated mathematical lock evidence is not transistor or full-chip qualification.',18,anchor='start')
panel(55,19400,2490,1260,'RF INSTANCE ONLY — SEPARATE PUMP, SLOW STORAGE AND VCO TUNING NETS','#f8f3fc')
block(100,19520,230,90,'REF_RF','qualified reference')
block(450,19520,220,120,'PFD / reset','REF, FB → UP, DN')
wire([(330,19555),(450,19555)],clock=True)
block(810,19510,250,140,'Charge pump','finite compliance')
for yy,name in [(19550,'UP'),(19610,'DN')]:
    wire([(670,yy),(810,yy)]);label(740,yy-12,name,16)
wire([(1060,19580),(1400,19580)],False)
label(1200,19555,'VCP',18,True)
resistor_h(1500,19580,'R3 ≈ 10.06 kΩ')
wire([(1400,19580),(1435,19580)],False)
wire([(1565,19580),(2120,19580)],False)
label(1910,19555,'VTUNE',18,True)
block(2120,19525,330,110,'RF VCO + bank','VTUNE / COARSE_CODE')
# Three capacitors and their distinct nodes. The lower branch is R–Cs.
capacitor_v(1160,19580,'Cf ≈ 21.19 pF');dot(1160,19580)
wire([(1160,19670),(1160,19970)],False)
wire([(1360,19580),(1360,19730),(1435,19730)],False);dot(1360,19580)
resistor_h(1500,19730,'R ≈ 10.18 kΩ')
wire([(1565,19730),(1660,19730)],False)
label(1655,19708,'VSLOW',16,True)
capacitor_v(1660,19730,'Cs ≈ 245.76 pF')
wire([(1660,19820),(1660,19970)],False)
capacitor_v(1910,19580,'C3 ≈ 1.248 pF');dot(1910,19580)
wire([(1910,19670),(1910,19970)],False)
wire([(1090,19970),(2040,19970)],False)
for x in [1160,1660,1910]:dot(x,19970)
label(1510,20005,'VSS_RF_PLL — capacitor return',17)
# Actual integer edge feedback, branched output; frequency counting is separate.
wire([(2300,19635),(2300,20095),(1820,20095)],clock=True);dot(2300,20095)
block(1480,20060,340,70,'Integer-edge divider','N[k], not an averaged ratio')
wire([(1480,20095),(550,20095),(550,19640)],clock=True)
label(1040,20078,'FB_RF',16,color='#80549c')
wire([(2300,20095),(2480,20095),(2480,19475),(2270,19475)],clock=True)
label(2265,19480,'→ LO phase drivers',17,anchor='end',color='#80549c')
block(100,19810,690,95,'Acquisition / retune sequencer','coarse search → settle → fine acquire → qualify')
# Distinct control routes, avoiding a single net shorting enable and bank bits.
wire([(790,19835),(870,19835),(870,19650)])
label(875,19705,'CP_EN',15,anchor='start')
wire([(790,19885),(960,19885),(960,20205),(2180,20205),(2180,19635)])
label(1840,20188,'COARSE_CODE[3:0]',16)
block(100,20260,400,80,'Reference-window counter','VCO/divided edges vs REF_RF')
wire([(2300,20095),(2380,20095),(2380,20400),(300,20400),(300,20340)],clock=True)
wire([(370,19555),(370,19490),(80,19490),(80,20300),(100,20300)],clock=True);dot(370,19555)
wire([(300,20260),(300,19905)])
label(308,20160,'COUNT / DONE',15,anchor='start')
block(650,20260,540,80,'Lock / compliance qualification','phase error, count error, node bounds')
wire([(620,19520),(620,19455),(2505,19455),(2505,20490),(1230,20490),(1230,20315),(1190,20315)])
label(905,20240,'PFD error / period observation',15)
wire([(920,20340),(920,20465),(580,20465),(580,19905)])
label(640,20450,'LOCK / FAULT → sequencer',16)
label(1260,20300,'VCP / VSLOW / VTUNE sensing: explicit wiring on final sheet',16,anchor='start')
label(1260,20338,'N[k] programming / divider timing: explicit wiring on final sheet',16,anchor='start')
label(100,20530,'Values are from the balanced mathematical candidate; tolerances, physical capacitance and noise remain unqualified.',17,anchor='start')
label(100,20570,'RF VCO output branches to divider, coarse counter and LO drivers; none of these destinations is a second oscillator.',17,anchor='start')
label(100,20610,'Window sensing and PFD observation are intended high-impedance taps, not loads qualified by these mathematical tests.',17,anchor='start')

panel(55,20700,2490,530,'RECENTERING — THREE INDEPENDENT FINITE DISCHARGE BRANCHES','#f8f3fc')
for x,name,rv in [(430,'VCP','≈ 9.44 kΩ'),(1210,'VSLOW','≈ 814 Ω'),(1990,'VTUNE','≈ 160.3 kΩ')]:
    label(x,20795,name,20,True)
    wire([(x,20815),(x,20865)],False)
    # Inline horizontal switch followed by resistor, routed to common bias return.
    wire([(x,20865),(x+78,20865)],False);switch(x+100,20865)
    wire([(x+122,20865),(x+155,20865)],False)
    resistor_h(x+220,20865,rv)
    wire([(x+285,20865),(x+330,20865),(x+330,21020)],False)
    label(x+95,20915,'CENTER_EN',15)
    wire([(x+100,20765),(x+100,20845)],clock=True);dot(x+100,20765)
wire([(180,20765),(2090,20765)],clock=True)
label(185,20752,'CENTER_EN ← sequencer',15,anchor='start')
wire([(250,21020),(2380,21020)],False)
for x in [760,1540,2320]:dot(x,21020)
label(1350,21060,'VBIAS_CENTER — finite buffered centering reference, not a fourth storage node',18)
label(100,21120,'Each branch uses Rcenter × Cnode ≈ 200 ns; switch resistance and reference impedance must be included in circuit refinement.',17,anchor='start')
label(100,21160,'Sequencer: hold pump → enable all shunts → wait / check → disable shunts → coarse settle → enable fine pump.',17,anchor='start')
label(100,21200,'The model stores voltage offsets about the operating point. Physical VBIAS_CENTER and headroom are still to be chosen.',17,anchor='start')

panel(55,21270,2490,620,'LOCAL SUPPLY CONDITIONING — OPTIONAL REGULATOR CIRCUIT CANDIDATE, REPEATED ONLY WHERE REQUIRED','#fff6f1')
block(100,21380,260,80,'VDD_DOMAIN','perimeter supply')
block(650,21380,320,80,'Series pass device','source → drain')
wire([(360,21420),(650,21420)],False)
wire([(970,21420),(2460,21420)],False)
label(1980,21396,'VDD_LOCAL → circuit supply ports',17)
block(650,21610,320,80,'Error amplifier','+ VREF_REG / − VSENSE')
wire([(810,21610),(810,21460)])
label(815,21530,'PASS_GATE',15,anchor='start')
block(100,21610,300,80,'Reference / startup','VREF_REG, ENABLE')
wire([(400,21640),(650,21640)])
wire([(1500,21420),(1500,21545)],False);dot(1500,21420)
# Resistive feedback represented explicitly with two separate resistor elements.
rect(1485,21545,30,55);label(1550,21580,'Rtop',16)
wire([(1500,21600),(1500,21660)],False);dot(1500,21630)
rect(1485,21660,30,55);label(1550,21695,'Rbottom',16)
wire([(1500,21630),(1110,21630),(1110,21665),(970,21665)])
label(1170,21610,'VSENSE',15)
wire([(1500,21715),(1500,21750)],False)
capacitor_v(1900,21420,'CLOCAL');dot(1900,21420)
wire([(1900,21510),(1900,21750)],False)
wire([(100,21750),(2410,21750)],False)
for x in [1500,1900]:dot(x,21750)
label(310,21782,'VSS_DOMAIN → local returns',17)
block(2040,21565,380,80,'Rail window monitor','VDD_LOCAL → PGOOD / FAULT')
wire([(2310,21420),(2460,21420),(2460,21600),(2420,21600)])
wire([(2220,21645),(2220,21685),(2400,21685)])
label(2040,21710,'PGOOD → reset / output-enable sequencer',15,anchor='start')
label(100,21835,'Amplifier compensation, pass-device polarity and stability versus load / CLOCAL require circuit design; direct supply bypass remains an option.',16,anchor='start')
label(55,21945,'Named ports join the existing sheets without extra package pins. Analog feedback, clocks and control buses are distinct nets.',18,anchor='start')


# Named terminals below are on-chip nets shared with the preceding PLL sheet.
# Each sensing channel is independent; common supply/reference rails are explicit.
panel(55,22010,2490,1420,'RF PLL — RATIO PROGRAMMING, NODE SENSING AND ACQUISITION INTERLOCKS','#f8f3fc')
block(100,22110,340,90,'RF ratio shadow registers','SPI / local configuration')
block(630,22110,400,90,'Atomic ratio commit','integer + fractional fields')
wire([(440,22155),(630,22155)])
label(535,22135,'RATIO / VALID',16)
block(1230,22110,430,90,'Fractional sequence state','integer modulus N[k]')
wire([(1030,22155),(1230,22155)])
label(1130,22135,'COMMIT',16)
block(1920,22110,490,90,'Integer-edge divider','RF VCO edges → FB_RF')
wire([(1660,22155),(1920,22155)])
label(1790,22135,'N[k]',17,True)
wire([(2410,22155),(2490,22155),(2490,22265),(1460,22265),(1460,22200)],clock=True)
label(1950,22248,'MODULUS_BOUNDARY → advance sequence',16,color='#80549c')
wire([(2140,22065),(2140,22110)],clock=True)
label(2140,22055,'RF_VCO_OUT',16)
wire([(2310,22200),(2310,22320),(2420,22320)],clock=True)
label(2400,22348,'FB_RF → PFD',16)
wire([(820,22065),(820,22110)])
label(820,22055,'RATIO_COMMIT ← sequencer',16)
label(100,22345,'Programming bus ≠ clock: modulus changes occur at a defined divider boundary. Circuit timing remains to be qualified.',17,anchor='start')
# All three storage nodes have their own high-impedance sense inputs.
for x,name in [(150,'VCP'),(930,'VSLOW'),(1710,'VTUNE')]:
    label(x,22420,name,19,True,anchor='start')
    wire([(x,22435),(x,22530),(x+160,22530)],False)
    block(x+160,22485,410,90,'Window comparator pair','LOW < node voltage < HIGH')
    wire([(x+300,22405),(x+300,22485)],False)
    label(x+300,22390,'VWIN_LOW / VWIN_HIGH',15)
    wire([(x+570,22530),(x+650,22530),(x+650,22625)])
    label(x+325,22615,name+'_IN_RANGE',16)
block(100,22625,2340,95,'Qualification logic — synchronized observations, counters and explicit bounds','VCP_IN_RANGE, VSLOW_IN_RANGE, VTUNE_IN_RANGE, PFD_ERROR, REF_COUNT, REF_PRESENT')
for x,name in [(410,'PFD_ERROR'),(1070,'REF_COUNT / DONE'),(1780,'REF_PRESENT')]:
    wire([(x,22775),(x,22720)])
    label(x,22800,name,17)
block(100,22900,630,130,'Acquisition / retune sequencer','hold → center → coarse → fine → qualify')
wire([(180,22720),(180,22900)])
label(195,22840,'NODES_OK / LOCK / FAULT',16,anchor='start')
# Individual outputs avoid implying a short between enables and bank data.
for yy,name in [(22920,'REF_HOLD → reference gate'),(22960,'CENTER_EN → three shunt switches'),(23000,'COARSE_CODE[3:0] → VCO bank')]:
    wire([(730,yy),(1130,yy)])
    label(1150,yy+6,name,17,anchor='start')
block(1830,22900,580,130,'Pump-enable interlock','fine request AND reference valid')
wire([(730,23015),(930,23015),(930,23105),(2090,23105),(2090,23030)])
label(1360,23085,'FINE_REQUEST',16)
wire([(2300,22775),(2300,22900)])
label(2300,22760,'REF_PRESENT',15)
wire([(1960,22825),(1960,22900)])
label(1960,22815,'CENTER_EN = 0',15)
wire([(2410,22965),(2490,22965),(2490,23170),(1880,23170)])
label(1870,23175,'CP_EN → charge pump',18,anchor='end')
label(100,23220,'Local services: window comparators use VDD_PLL / VSS_PLL and finite buffered thresholds; logic uses its own supply domain.',17,anchor='start')
label(100,23260,'Named ports are identical nets across sheets, not extra IOs. Sense input capacitance, offset, loading and synchronization remain design work.',17,anchor='start')
label(100,23300,'Interlock requires CENTER_EN low before enabling the pump; centering and active phase correction must not contend.',17,anchor='start')
label(100,23340,'This expands candidate block connectivity. It does not assert completed transistor wiring, noise closure, or a fabricated implementation.',17,anchor='start')

# Latest connected mathematical candidate; detailed physical realization remains open.
rf_start = len(A)
panel(55,23530,2490,1680,'CURRENT RF CANDIDATE — ONE LOADED NETWORK FOR PAD, CALIBRATION AND LOOPBACK','#f1f8f5')
label(90,23610,'RF active mode; wired payload disabled. Experimental connectivity, not completed transistor circuitry or a scaled layout.',19,anchor='start')
block(110,23700,300,90,'I/Q DAC + reconstruction','paired updates / correction')
block(480,23700,280,90,'I/Q mixers + RF driver','nonlinear source; common LO')
wire([(410,23745),(480,23745)])
block(825,23710,155,70,'Source R','50 ohm assumed')
wire([(760,23745),(825,23745)]);wire([(980,23745),(1110,23745)],False);dot(1110,23745)
label(1110,23708,'INTERNAL_P/N',17,True)
block(1240,23710,260,70,'Output isolation switch','ON: 5 ohm; OFF: 1 Mohm')
wire([(1110,23745),(1240,23745)]);wire([(1500,23745),(1680,23745)],False);dot(1680,23745)
label(1680,23708,'PAD_P/N',17,True)
block(1830,23710,230,70,'Protection / pad','parasitic loading')
wire([(1680,23745),(1830,23745)]);wire([(2060,23745),(2405,23745)])
pin(2405,23712,180,'RF_TX_P/N','existing 2 terminals')
cap(1110,23820);wire([(1110,23745),(1110,23802)],False);label(1110,23885,'50 fF internal',16)
cap(1680,23820);wire([(1680,23745),(1680,23802)],False);label(1680,23885,'100 fF pad',16)
label(1880,23850,'50 ohm external termination',17)
label(1880,23885,'Output-switch feedthrough: 1 fF',16)
dot(1010,23745);dot(1050,23745);dot(1740,23745)
# Dummy branch is a separate switch and retained analog node.
wire([(1110,23745),(1050,23745),(1050,24000),(1210,24000)])
block(1210,23965,290,70,'Dummy-load switch','ON: 5 ohm; OFF: 1 Mohm')
wire([(1500,24000),(1680,24000)],False);dot(1680,24000)
block(1810,23965,300,70,'Dummy termination','50 ohm; internal, no IO')
wire([(1680,24000),(1810,24000)])
cap(1680,24070);wire([(1680,24000),(1680,24052)],False)
label(1880,24100,'20 fF node; 10 fF switch feedthrough',16)
# Pre-isolation monitor remains observable during quiet calibration.
wire([(1110,23745),(1010,23745),(1010,24200),(920,24200)])
block(640,24165,280,70,'Monitor coupling R','1 kohm; pre-isolation tap')
wire([(640,24200),(490,24200)],False);dot(490,24200)
label(490,24140,'MONITOR_P/N',17,True)
cap(490,24270);wire([(490,24200),(490,24252)],False)
label(490,24325,'50 fF + 10 kohm shunt',16)
block(110,24385,310,80,'Power detector','finite response / retained state')
wire([(490,24200),(450,24200),(450,24360),(265,24360),(265,24385)])
block(480,24385,310,80,'Buffered readout','20 ns settling assumption')
wire([(420,24425),(480,24425)])
block(850,24385,310,80,'I-channel diagnostic mux','exclusive calibration ownership')
wire([(790,24425),(850,24425)])
block(1220,24385,310,80,'Shared I ADC','finite conversion + VREF load')
wire([(1160,24425),(1220,24425)])
block(1600,24385,350,80,'Calibration controller','nine probes / epoch / commit')
wire([(1530,24425),(1600,24425)])
block(2020,24385,390,80,'Relative I/Q correction','does not recover absolute pad gain')
wire([(1950,24425),(2020,24425)])
wire([(2215,24385),(2215,23655),(260,23655),(260,23700)])
label(1350,23642,'COMMITTED CORRECTION → DAC CODE PATH; no attenuation normalization',16)
# Physical pad loopback branches independently from calibration monitor.
wire([(1680,23745),(1740,23745),(1740,23910),(2460,23910),(2460,24540),(330,24540),(330,24600)])
label(2180,24525,'LOOPBACK FROM PAD; finite network state',17,True)
block(110,24600,440,80,'RF input / loopback selection','RF_RX_P/N front end OR loaded pad')
block(620,24600,310,80,'I/Q receive mixers','autonomous LO / image terms')
wire([(550,24640),(620,24640)])
block(1000,24600,510,80,'I/Q PGA + fifth-order LPF','Butterworth; cutoff 9.157407 MHz')
wire([(930,24640),(1000,24640)])
block(1580,24600,400,80,'I/Q ADCs → RX queues','shared I diagnostic selection above')
wire([(1510,24640),(1580,24640)])
block(2050,24600,360,80,'Host / local capture','existing GPIO / SPI terminals')
wire([(1980,24640),(2050,24640)])
label(1255,24720,'Each I/Q filter: two second-order sections + one real pole; circuit realization remains open.',18)
block(110,24800,650,90,'Shared reference and supply model','ADC / DAC charge loads; gain and oscillator coupling')
wire([(110,24845),(80,24845),(80,24495),(1375,24495),(1375,24465)])
label(1080,24485,'VREF_I_ADC / calibration loading',16)
wire([(760,24865),(1780,24865),(1780,24680)])
label(1250,24898,'Converter reference / supply services',16)
label(90,24970,'RC values label mathematical assumptions. Differential conductors are bundled here; no additional external terminals.',18,anchor='start')
label(90,25015,'Pad observation reads PAD_P/N directly. Detector reads the pre-switch MONITOR_P/N node; these are not the same net.',18,anchor='start')
label(90,25060,'Output-off / dummy-on switching retains capacitor state. Quiet calibration uses relative-gain fitting, with explicit commit.',18,anchor='start')
label(90,25105,'Still open: loaded waveform quality, driver current / supply limits, transistor realization, package and parasitic qualification.',18,anchor='start')


rf_end = len(A)
panel(55,25340,2490,1060,'OPERATING POLICY — ONE CHIP, RF OR WIRED ACTIVE; SHARE PHYSICAL RESOURCES','#f8f3fc')
block(120,25460,540,100,'SPI / host mode request','NONE / RF / WIRED')
block(820,25460,850,100,'Exclusive-engine ownership / interlock','stop → isolate → release → configure → settle → qualify')
wire([(660,25510),(820,25510)])
block(1850,25460,540,100,'Shared service ownership','per-mode state / fresh calibration validity')
wire([(1670,25510),(1850,25510)])
block(330,25710,720,100,'RF ACTIVE','RF TX/RX + required local clock / analog services')
block(1530,25710,720,100,'WIRED ACTIVE','full-duplex lane; TX clock and independent RX CDR')
wire([(1050,25560),(1050,25630),(690,25630),(690,25710)])
wire([(1450,25560),(1450,25630),(1890,25630),(1890,25710)])
label(1280,25765,'ONE ENABLE ONLY',22,True)
block(260,25930,2050,120,'Share host interface, memory, calibration, reference / bias and diagnostic services','Evaluate one retunable TX PLL and reusable analog tiles; preserve each mode’s timing and electrical requirements')
wire([(690,25810),(690,25930)]);wire([(1890,25810),(1890,25930)])
label(100,26130,'Additional sharing is encouraged. Separate RF/wired front ends remain provisional; switch loading, tuning range and noise need evidence.',19,anchor='start')
label(100,26180,'Existing separate PLL / front-end sheets show candidate structures, not a requirement to duplicate every physical resource.',19,anchor='start')
label(100,26230,'No extra IOs are introduced. Existing pin and bandwidth allocations remain provisional until exclusive-mode rebudgeting.',19,anchor='start')
label(100,26280,'Behavioral ownership and handovers tested; physical / RTL interlocks remain open. Concurrent traffic is optional stress.',19,anchor='start')
label(100,26330,'This policy supersedes earlier simultaneous-operation requirements; both capabilities remain required on the first fabricated chip.',19,anchor='start')

panel(55,26630,2490,1560,'CONFIGURABLE CIRCUITS — SHARED PADS, LOCAL TIMING AND RF CHANNEL CONTEXTS','#f2f5fc')
label(100,26705,'Design intent: generic resource controls and electrical branches still require full RTL / circuit qualification.',20,True,anchor='start')
pin(80,26800,280,'WIRE_RX / USB D+/D-','same two terminals')
block(440,26800,300,65,'Protection / isolation','finite C_off and leakage')
wire([(360,26832),(440,26832)],False)
wire([(740,26832),(805,26832)],False);dot(805,26832)
block(900,26800,460,65,'Serial Rterm / CTLE / slicer','SATA / DP RX / PCIe / Ethernet')
wire([(805,26832),(900,26832)])
block(1550,26800,360,65,'RX CDR / deserializer','rate and SSC qualification')
wire([(1360,26832),(1550,26832)])
block(2130,26800,320,65,'RX queue','existing host path')
wire([(1910,26832),(2130,26832)])
block(900,26970,460,85,'USB HS driver / RX / squelch','current drive + switched termination')
wire([(805,26832),(805,27012),(900,27012)],False)
block(900,27140,460,85,'USB FS/LS drive + receivers','single-ended states + selectable pulls')
wire([(805,27012),(805,27182),(900,27182)],False);dot(805,27012)
block(1550,26970,450,255,'Timed line-state / bit service','local transitions; FPGA owns protocol')
wire([(1360,27012),(1550,27012)],False)
wire([(1360,27182),(1550,27182)],False)
block(2130,27030,320,125,'Existing host frame /8','same queues + GPIO pins')
wire([(2000,27092),(2130,27092)],False)
block(440,27330,520,85,'Resource / role / output interlock','stop, isolate, settle, qualify, enable')
wire([(700,27330),(700,27265),(1110,27265),(1110,27225)],clock=True)
wire([(960,27372),(1750,27372),(1750,27225)],clock=True)
label(1100,27435,'USB mode: WIRE_TX high-Z; no serial AC coupling on D+/D-.',18,anchor='start')
label(100,27500,'FPGA board sidebands: USB VBUS switch / sense; DP AUX transceiver / HPD. No extra chip terminals.',20,anchor='start')
block(180,27620,470,100,'Channel / gain / filter contexts','finite memory + calibration validity')
block(850,27620,470,100,'Timed context / direction commit','keep LO warm during packet exchange')
block(1550,27620,730,100,'RF LO + LPF/PGA + ADC/DAC + TX/RX gates','existing local RF paths; no additional RF chain')
wire([(650,27670),(850,27670)],clock=True)
wire([(1320,27670),(1550,27670)],clock=True)
block(850,27830,470,100,'Ready / overload / timestamps','shared observation and host events')
wire([(1915,27720),(1915,27880),(1320,27880)])
wire([(850,27880),(415,27880),(415,27720)],clock=True)
label(100,28015,'RF: HE20 Wi-Fi / LE / BR-EDR / O-QPSK / LoRa. Independent waveform, hopping and turnaround gates.',20,anchor='start')
label(100,28065,'Serial: 0.480–2.50 Gb/s; video x10 fractional references; HD-SDI 1.485 and 1.485/1.001 Gb/s (external coax).',20,anchor='start')
label(100,28115,'One resource configuration; DP one RBR lane; RF one 20 MHz stream. 50 terminals, 12.92 mm² allocation ceiling.',20,anchor='start')
label(100,28165,'Shared-pad capacitance and FPGA response latency are feasibility gates, not assumptions of successful support.',20,anchor='start')

video_start = len(A)
# Board-level assembly: unchanged single-lane die instantiated three times.
label(55,28380,'HDMI / DVI — THREE IDENTICAL SINGLE-LANE DIES',30,True,'start')
label(55,28425,'Board assembly, not extra lanes on the 1x1 die. Source shown; sink reverses data direction.',20,anchor='start')
block(120,28520,530,1020,'External FPGA','TMDS encoding / packets / deskew','#edf2fc')
for i,y in enumerate((28600,28900,29200)):
    block(1050,y,700,180,f'Chip {i}: existing wired lane','host FIFO > serializer / sampler > DC pad','#f0f8f4')
    wire([(650,y+90),(1050,y+90)],False)
    label(845,y+55,'10-bit host + clock',18)
    wire([(1750,y+90),(2240,y+90)],False)
    block(2240,y+45,300,90,f'TMDS DATA {i}','one differential pair')
    label(1395,y+150,'REF_IN / x10 word clock / phase control',17)
block(1040,29600,700,130,'External clock driver / receiver + fanout','TMDS clock pair; 74.25/1.001–148.5 MHz','#f9f1fb')
wire([(385,29540),(385,29665),(1040,29665)],False,True)
wire([(1740,29665),(2240,29665)],False,True)
block(2240,29615,300,100,'TMDS CLOCK','fourth cable pair')
wire([(950,29665),(950,28510),(1400,28510),(1400,28600)],False,True)
wire([(1040,29665),(950,29665)],False,True)
for y in (28900,29200):wire([(950,y-30),(1400,y-30),(1400,y)],False,True)
label(55,29810,'Each die: 50 terminals, one wafer.space slot; RF payload off. FPGA/board owns DDC, HPD, 5 V and optional CEC.',19,anchor='start')
label(55,29860,'720p / 1080p: integer and /1.001 clocks; intermediate x10 rates. Framed GPIO links; no chip protocol IDs.',19,anchor='start')
label(55,29910,'Open gates: DC pad / ESD, x10 clock and word phase, cross-die skew, FIFO / CDC, independent video compliance.',19,anchor='start')

put('</g></svg>')
Path(__file__).with_name('transceiver-block-diagram.svg').write_text('\n'.join(A)+'\n')

# Focused sheets reuse only their own elements, plus shared SVG definitions.
def write_detail(filename, start, end, y):
    header = A[0].replace('height="30000" viewBox="0 0 2600 30000"',
                          f'height="1750" viewBox="0 {y} 2600 1750"', 1)
    drawing = [header, *A[start:end], A[-1]]
    Path(__file__).with_name(filename).write_text('\n'.join(drawing) + '\n')

write_detail('transceiver-rf-loaded-detail.svg', rf_start, rf_end, 23500)
write_detail('transceiver-video-detail.svg', video_start, len(A) - 1, 28250)
