"""Extracted LNA + I/Q passive mixers + TIAs: two-tone IIP3 and blocker desensitization.
Source: 100 ohm differential (ideal balun), board match per tb.board_match (as in the prior chain
evidence) or none. Power in dBm = available power from the 100 ohm source."""
import sys, json, math
from pathlib import Path
R='/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx'
sys.path.insert(0,R)
import tb
NOM=('typical',27,3.3)
def emf(dbm): return math.sqrt(8*100*1e-3*10**(dbm/10))
def deck(w, tones, match, tstop, tstart, corner=NOM, view='ext'):
    vdd=corner[2]
    nl,ni,nq=(tb.netlist(w,b,view) for b in ('lna','rxmix_i','rxmix_q'))
    srcs='\n'.join(f'Vs{k} s{k} s{k+1} DC 0 SIN(0 {a} {f})' for k,(f,a) in enumerate(tones))
    n=len(tones)
    src=('Rsp s_p sp 50\nRsn s_n sn 50\n'+tb._match_net(match)) if match else 'Rsp s_p rf_in_p 50\nRsn s_n rf_in_n 50\n'
    return f""".include {nl}
.include {ni}
.include {nq}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib1 vib ib1 10u
Ib2 vib ib2 10u
Ib3 vib ib3 10u
Ven en 0 {vdd}
Vgl gain_lo 0 0
Vby byp 0 0
Vio island_off 0 0
Venm enm 0 {vdd}
{tb._ofs(0, vdd, 'i')}
{tb._ofs(0, vdd, 'q')}
{srcs}
Vend s{n} 0 0
Ep s_p 0 s0 0 0.5
En s_n 0 s0 0 -0.5
{src}Cpp rf_in_p 0 0.5p
Cpn rf_in_n 0 0.5p
Blip lip 0 V={vdd/2}+{vdd/2}*tanh(8*sin(2*pi*2.4e9*time))
Blin lin 0 V={vdd/2}-{vdd/2}*tanh(8*sin(2*pi*2.4e9*time))
Blqp lqp 0 V={vdd/2}-{vdd/2}*tanh(8*cos(2*pi*2.4e9*time))
Blqn lqn 0 V={vdd/2}+{vdd/2}*tanh(8*cos(2*pi*2.4e9*time))
{tb._lna_trim(vdd)}
XL rf_in_p rf_in_n rfo_p rfo_n rfq_p rfq_n ib1 en gain_lo byp ct0 ct1 ct2 se rt island_off nb vdcm VDD 0 pt_lna
XI rfo_p rfo_n lip lin bip bin ib2 enm ofs0i ofs1i ofs2i ofs3i ofs4i ofs_signi island_off avi abi VDD 0 pt_rxmix_i
XQ rfq_p rfq_n lqp lqn bqp bqn ib3 enm ofs0q ofs1q ofs2q ofs3q ofs4q ofs_signq island_off avq abq VDD 0 pt_rxmix_q
Cbi1 bip 0 1p
Cbi2 bin 0 1p
Cbq1 bqp 0 1p
Cbq2 bqn 0 1p
.save v(bip) v(bin)
.tran 10p {tstop} {tstart} 10p
.control
run
let vi=v(bip)-v(bin)
wrdata lin.dat vi
.endc
"""
def run(tag, tones_dbm, meas_f, match, tstop=1.2e-6, tstart=0.2e-6, corner=NOM):
    w=Path('lin_'+tag).resolve(); w.mkdir(exist_ok=True)
    tones=[(f, emf(p)) for f,p in tones_dbm]
    tb.run(w,'lin.cir',deck(w,tones,match,tstop,tstart,corner),corner,timeout=20000)
    return {f: tb.tone(w/'lin.dat',f,tstart,tstop) for f in meas_f}
if __name__=='__main__':
    mode=sys.argv[1]; p=float(sys.argv[2])
    w=Path('lin_lna').resolve(); w.mkdir(exist_ok=True)
    act=tb.lna_ac(w,'ext',NOM,'active'); m=tb.board_match(complex(act['zin_re_ohm'],act['zin_im_ohm']))
    LO=2.4e9
    if mode=='iip3':      # out-of-band two tone: LO+20 MHz, LO+37 MHz -> IM3 at LO+3 MHz
        r=run(f'iip3_{p}',[(LO+20e6,p),(LO+37e6,p),(LO+3e6+0.0,-200)],[20e6,37e6,3e6],m)
        # reference small-signal gain at 3 MHz from a separate wanted-tone run
        g=run('ref3',[(LO+3e6,-60)],[3e6],m)[3e6]/emf(-60)
        a_im3=r[3e6]; pin_im3=20*math.log10(a_im3/g/emf(p))+p   # IM3 referred to input (dBm)
        iip3=p+(p-pin_im3)/2
        print(json.dumps(dict(mode=mode,p_dbm=p,im3_out_v=a_im3,gain_3mhz_db=20*math.log10(g),im3_in_dbm=pin_im3,iip3_dbm=iip3,tones_out_v=[r[20e6],r[37e6]])))
    elif mode=='inband':  # in-band two tone LO+3, LO+4 -> IM3 at LO+2, LO+5
        r=run(f'ib3_{p}',[(LO+3e6,p),(LO+4e6,p)],[3e6,4e6,2e6,5e6],m)
        a1=(r[3e6]+r[4e6])/2; a3=(r[2e6]+r[5e6])/2
        iip3=p+20*math.log10(a1/a3)/2
        print(json.dumps(dict(mode=mode,p_dbm=p,fund_v=a1,im3_v=a3,iip3_dbm=iip3)))
    elif mode=='block':   # wanted -60 dBm at LO+3 MHz, CW blocker at LO+off
        off=float(sys.argv[3])
        g0=run('ref3',[(LO+3e6,-60)],[3e6],m)[3e6]
        r=run(f'blk_{off/1e6:g}_{p}',[(LO+3e6,-60),(LO+off,p)],[3e6],m)
        print(json.dumps(dict(mode=mode,blocker_dbm=p,offset_hz=off,desense_db=20*math.log10(g0/r[3e6]))))
