import subprocess,itertools,json,numpy as np,os
M='/foss/pdks/gf180mcuD/libs.tech/ngspice'
def hdr(c,t):
    c={'tt':'typical','ss':'ss','ff':'ff'}[c]
    return f".lib {M}/sm141064.ngspice {c}\n.lib {M}/sm141064.ngspice res_typical\n.include {M}/design.ngspice\n.temp {t}\n.include pt_decap_tile_ext.spice\n"
def ng(name,deck):
    open(name+'.cir','w').write(deck)
    subprocess.run(['docker','run','--rm','--network','none','--user','1000:1000','-e','HOME=/tmp','-v',os.getcwd()+':/w','-w','/w','--entrypoint','/bin/bash','sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305','-lc',f'ngspice -b {name}.cir > {name}.log 2>&1'])
res={}
# AC: 1 tile
for c,t,v in [('tt',27,3.3)]+[(c,t,v) for c in ('tt','ss','ff') for t in (22,32) for v in (3.15,3.35)]:
    n=f'ac_{c}_{t}_{v}'
    ng(n,hdr(c,t)+f"V1 vdd 0 DC {v} AC 1\nX1 0 vdd pt_decap_tile\n.control\nop\nprint v(x1.a_200_1680#) v(x1.a_320_300#)\nac dec 10 1e6 2e9\nwrdata {n}.dat i(V1)\n.endc\n.end\n")
    d=np.loadtxt(n+'.dat'); f=d[:,0]; Y=-(d[:,1]+1j*d[:,2])
    pick=lambda fr: int(np.argmin(abs(f-fr)))
    res[n]={f'{fr:g}':dict(C_pF=float(Y[pick(fr)].imag/(2*np.pi*f[pick(fr)])*1e12),ESR_ohm=float((1/Y[pick(fr)]).real),Q=float(Y[pick(fr)].imag/Y[pick(fr)].real)) for fr in (1e6,1e7,1e8,1e9,2e9)}
    res[n]['op']=open(n+'.log').read().split('v(x1.a_200_1680#)')[-1][:120].split()
# leakage
for c,t,v in [('tt',27,3.3),('ff',85,3.63),('ff',32,3.35)]:
    n=f'leak_{c}_{t}_{v}'
    ng(n,hdr(c,t)+f"V1 vdd 0 DC {v}\nX1 0 vdd pt_decap_tile\n.control\nop\nprint i(V1) v(x1.a_200_1680#) v(x1.a_320_300#)\n.endc\n.end\n")
    res[n]=open(n+'.log').read()[-400:]
# ramps and over-voltage pulse
for n,src,stop in [('ramp10n','PWL(0 0 10n 3.63 2u 3.63)','2u'),('ramp1u','PWL(0 0 1u 3.63 4u 3.63)','4u'),
                   ('pulse5v','PWL(0 3.3 100n 3.3 100.1n 5 102.1n 5 102.2n 3.3 300n 3.3)','300n')]:
    ng(n,hdr('tt',27)+f"VS s 0 {src}\nR1 s vdd 1\nX1 0 vdd pt_decap_tile\n.control\ntran 0.05n {stop}\nwrdata {n}.dat v(vdd) v(x1.a_200_1680#) v(x1.a_320_300#)\n.endc\n.end\n")
    d=np.loadtxt(n+'.dat'); vdd,gb,g=d[:,1],d[:,3],d[:,5]
    res[n]=dict(final_vdd=float(vdd[-1]),final_GB=float(gb[-1]),final_G=float(g[-1]),
      max_VDD_minus_GB=float((vdd-gb).max()),max_G_minus_VSS=float(g.max()),max_G_minus_GB=float(abs(g-gb).max()))
json.dump(res,open('results.json','w'),indent=1)
