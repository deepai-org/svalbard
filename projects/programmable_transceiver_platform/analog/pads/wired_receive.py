"""Shared RX/USB pad candidate; analog front ends attach at explicit ports.

All branches remain physically connected. Controls are voltages supplied by the
core, not protocol names. Dimensions are candidate sizes, not achieved specs.
"""
import json
from circuits import Capacitor, Circuit, Mos, Resistor, foundation_devices
from design import PROJECT, resolve


def build(*, hs_units=14, fs_high_units=24, differential_units=5, differential_width_um=20., fs_high_width_um=20., fs_series_geometry_um=None,
          termination_geometry_um=None, high_side_fast_off=False, hs_mirror_reference=False, pad_side_6v=False,
          termination_switch_units=8, termination_trim=None, term_gate_drive=1., fast_off_width_um=4., control_width_um=2., ls_slow=None):
    # Stress-safe USB revision (opt-in; defaults reproduce the canonical cell):
    # termination_geometry_um=(w, l, n): n parallel unsalicided ppolyf_u segments
    #   (ppolyf_s 24 ohm spans 14..60 ohm across res corners; ppolyf_u ~+/-19 %)
    # high_side_fast_off: well-sourced PMOS pulls each FS high-side gate to its well
    #   when the enable falls (the bleed chain alone turns it off in ~100 ns)
    # hs_mirror_reference: diode-connected reference PMOS on HS_PBIAS; HS_PBIAS becomes
    #   a current input (I_leg / hs_units) from the trimmed bias DAC
    # PD21 (HBM item a), opt-in: every 3.3 V device with a terminal that follows the pad during an unpowered
    #   2 kV event becomes a 6 V device: shunt/termination switches (USB-only after the SATA/PCIe split, so
    #   TERM_VCM = 0 V and 6 V NMOS switches keep full gate drive), divider ground, pull-down, and on each
    #   back-to-back high side the VDD-side PMOS (its gate follows the floating well, i.e. the pad - 0.7 V)
    #   plus the well restore / fast-off PMOS and the supply-gated ground switch. The pad-side PMOS keeps
    #   3.3 V oxide: all its terminals stay within one junction drop of each other.
    # PD28 (USB on 6 V, opt-in; defaults reproduce the canonical cell): termination_switch_units = parallel
    #   20 um shunt switches per leg (8 canonical); termination_trim = dict(poly=(w, l), switch_w=um, bits=n):
    #   binary-weighted parallel units (poly width and switch width x 2^k) from PAD to TERM_VCM, gated by
    #   TERM_TRIM<k> (digital supplies trim[k] AND term_en, as for the HS pair, PD27). Base + trim brings the
    #   ppolyf_u +/-16 % corner spread back inside 45 ohm +/- 10 %.
    # PD28 LS slow-edge mode (opt-in; None reproduces the canonical cell): ls_slow = dict(high_a_units=a, low_a_units=k).
    #   New port LS_SLOW (3.3 V, active high; digital usbfs.config.ls_slow). Each FS high side keeps its series R,
    #   drain node and floating well; its PMOS units are split into an always-enabled A part (a units) and a B part
    #   (the rest) with its own gate, bleed and control path, whose control has a series NMOS gated by LS_SLOW_B.
    #   The FS low side (base shunt bank) is split the same way: k switches (A) driven by their own inverter of the
    #   OR gate, the rest (B) by NOR(TERM_OR_B, LS_SLOW). LS_SLOW = 0: A + B = the canonical drivers and the canonical
    #   termination (no added pad-side device); LS_SLOW = 1: only A drives (LS edges).
    # PD46 (PD44 laid out, opt-in): ls_slow = dict(miller=dict(c_um=s, control_w=w, ...)) replaces the A/B split by
    #   load-independent Miller-integrated LS edges. No B units: every FS unit / base shunt switch stays on one gate.
    #   High side: the gate pull-down (POWER NMOS) gets a series saturated limiter nfet_03v3 mirrored from HS_PBIAS
    #   (LSBP/LSBN, ~50 uA) bypassed by an NMOS on LS_SLOW_B. Low side: TERM_GATE is driven by one inverter whose
    #   PMOS source sits on a PMOS limiter (gate HS_PBIAS) bypassed by a PMOS on LS_SLOW. Per driver a square
    #   s x s um MIM (top = M node, bottom = the gate) joins the driver's pad-side node (FS_OUT / TERM_R) through a
    #   pad-side transmission gate (nfet_06v0 gate LS_SLOW, pfet_06v0 gate LS_SLOW_B, body = the leg's FS well),
    #   closed only with LS_SLOW = 1. LS_SLOW = 0: limiters bypassed, TGs open (FS/HS/termination as v9).
    #   Needs the HS bias reference on (HS_PBIAS = mirror gate) in LS mode.
    N6 = ('nfet_06v0', .7) if pad_side_6v else ('nfet_03v3', .28)
    lsm = (ls_slow or {}).get('miller')
    P6 = ('pfet_06v0', .55) if pad_side_6v else ('pfet_03v3', .28)
    if any(type(n) is not int or n < 1 for n in (hs_units,fs_high_units,differential_units)):
        raise ValueError('Positive integer unit counts required')
    if not .8<=differential_width_um<=20.:
        raise ValueError('Differential switch unit width must be 0.8..20 um')
    if not .8<=fs_high_width_um<=20:raise ValueError('FS width must fit unit geometry')
    if fs_series_geometry_um is not None and (len(fs_series_geometry_um)!=2 or min(fs_series_geometry_um)<=0):raise ValueError('Invalid FS resistor geometry')
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    blocks=architecture['blocks']
    required=resolve()['families']['wired_receive_usb']
    devices=[]
    ports=['PAD_P','PAD_N','VDD','VSS','TERM_VCM','TERM_ENABLE','DIFF_ENABLE','DIV_ENABLE','BYPASS_ENABLE',
           'RX_P','RX_N','HS_PBIAS','HS_P','HS_N','FS_HIGH_P','FS_HIGH_N','FS_LOW_P','FS_LOW_N',
           'PULLUP_P','PULLUP_N','PULLDOWN_P','PULLDOWN_N']
    if termination_trim:
        ports += [f'TERM_TRIM{k}' for k in range(termination_trim['bits'])]
    if ls_slow:
        ports += ['LS_SLOW']
    def mos(name,d,g,s,b,model='nfet_03v3',w=8.,l=.28):
        devices.append(Mos(name,(d,g,s,b),model,w,l))
    def resistor(name,a,b,ohm,model='ppolyf_u_1k',width=1.):
        sheet=1000 if model=='ppolyf_u_1k' else 7.3
        devices.append(Resistor(name,(a,b,'VSS'),model,width,round(ohm/sheet*width,2)))
    def high_side(name,destination,enable,resistance,units,width=20.,series_geometry=None,control_gate=None,share=None):
        # Back-to-back PMOS with a common floating source/well. Each drain
        # faces a different endpoint, so neither body diode alone backfeeds
        # VDD. Passive gate-to-source bias keeps the pair off without power.
        well=name+'_WELL';gate=name+'_GATE';out=name+'_OUT'
        if share is not None:   # PD28 LS slow B part: own gate/control/bleed, the A part's well, drain node and series R
            well,out=share
        for i in range(units):
            mos(f'{name}_SUP_{i}','VDD',gate,well,well,P6[0],width,P6[1])
            mos(f'{name}_PAD_{i}',out,gate,well,well,'pfet_03v3',width,.28)
        # Series ground switch opens when the local supply disappears, even
        # if the external enable remains asserted. No ideal power-good signal.
        # The floating gate can undershoot during VDD collapse while a
        # retained request remains high; use the 6V gate-oxide device here.
        mos(name+'_CONTROL',gate,enable,name+'_CONTROL_S','VSS','nfet_06v0',(lsm['control_w'] if lsm else control_width_um) if name.startswith('FS_') else 2.,.7)  # PD28 opt-in (2 canonical)
        power_d=name+'_CONTROL_S'
        if control_gate is not None:   # PD28 LS slow: series enable in the control path of the B high side
            power_d=name+'_CONTROL_LS'
            mos(name+'_LSGATE',name+'_CONTROL_S',control_gate,power_d,'VSS','nfet_03v3',max(4.,2.*control_width_um),.28)
        if lsm and name.startswith('FS_'):   # PD46: series limiter || bypass between CONTROL_S and the POWER drain
            for k in range(2):   # 2 x control_w (one 2*control_w device would overflow the 26 um placement row)
                mos(f'{name}_POWER_{k}',name+'_CTLX','VDD','VSS','VSS',N6[0],lsm['control_w'],N6[1])
            mos(name+'_LIMIT',name+'_CONTROL_S','LSNB',name+'_CTLX','VSS','nfet_03v3',lsm['limit_n'][0],lsm['limit_n'][1])
            mos(name+'_LIMIT_BYPASS',name+'_CONTROL_S','LS_SLOW_B',name+'_CTLX','VSS','nfet_03v3',lsm['bypass_n_w'],.28)
        else:
            mos(name+'_POWER',power_d,'VDD','VSS','VSS',N6[0],max(4.,2.*control_width_um) if name.startswith('FS_') else 4.,N6[1])
        # A falling VDD turns on a well-referenced PMOS that restores the
        # pass gates toward their floating source, avoiding a resistor-only
        # 100kohm discharge delay. Its body follows the same local well.
        mos(name+'_RESTORE',gate,'VDD',well,well,P6[0],4.,P6[1])
        if high_side_fast_off and name.startswith('FS_'):
            mos(name+'_FASTOFF',gate,enable,well,well,P6[0],fast_off_width_um,P6[1])  # PD28: width opt-in (4 canonical)
        previous=well
        for i in range(8):
            following=gate if i==7 else f'{name}_BLEED_{i}'
            resistor(f'{name}_BLEED_{i}',previous,following,12500)
            previous=following
        if share is not None:
            return
        if series_geometry is None:
            resistor(name+'_R',out,destination,resistance,'ppolyf_s' if resistance<100 else 'ppolyf_u_1k')
        else:
            devices.append(Resistor(name+'_R',(out,destination,'VSS'),'ppolyf_s',*series_geometry))
    def shared_low_enable(leg):
        # Static CMOS complex gate: TERM_ENABLE OR (FS_LOW AND VCM_LOW_OK).
        # Bias qualification blocks a lone FS-low request at serial common
        # mode; TERM_ENABLE remains a distinct intentional shunt request.
        # PD28 term_gate_drive (opt-in): scales the local TERM_GATE driver for the 6 V shunt bank gate load
        # (output stage x term_gate_drive, capped at 20 um; first stage x sqrt). 1.0 = canonical sizes.
        g2=min(term_gate_drive,2.5);g1=round(g2**.5,3) if term_gate_drive!=1. else 1.
        low='FS_LOW_'+leg;inv='TERM_OR_'+leg+'_B';out='TERM_GATE_'+leg;series='TERM_OR_'+leg+'_S'
        mos('TERM_OR_'+leg+'_N0',inv,'TERM_ENABLE','VSS','VSS',w=2.*g1)
        mos('TERM_OR_'+leg+'_N1',inv,low,'TERM_OR_'+leg+'_NS','VSS',w=2.*g1)
        mos('TERM_OR_'+leg+'_QUAL_N','TERM_OR_'+leg+'_NS','VCM_LOW_OK','VSS','VSS',w=4.*g1)
        mos('TERM_OR_'+leg+'_P0',series,'TERM_ENABLE','VDD','VDD','pfet_03v3',4.*g1,.28)
        mos('TERM_OR_'+leg+'_P1',inv,low,series,'VDD','pfet_03v3',4.*g1,.28)
        mos('TERM_OR_'+leg+'_QUAL_P',inv,'VCM_LOW_OK',series,'VDD','pfet_03v3',4.*g1,.28)
        if lsm:
            # PD46: one inverter drives every base switch; PMOS source on the LS limiter || bypass
            mos('TERM_OR_'+leg+'_OUT_N',out,inv,'VSS','VSS',w=lsm['inv_n_w'])
            mos('TERM_OR_'+leg+'_OUT_P',out,inv,'TERM_LS_'+leg+'_S','VDD','pfet_03v3',lsm['inv_p_w'],.28)
            mos('TERM_LS_'+leg+'_LIMIT','TERM_LS_'+leg+'_S','HS_PBIAS','VDD','VDD','pfet_03v3',lsm['limit_p'][0],lsm['limit_p'][1])
            mos('TERM_LS_'+leg+'_LIMIT_BYPASS','TERM_LS_'+leg+'_S','LS_SLOW','VDD','VDD','pfet_03v3',lsm['bypass_p_w'],.28)
        elif ls_slow:
            # base bank split: B switches (all but low_a_units) on NOR(inv, LS_SLOW) = the canonical driver plus an
            # LS_SLOW pull-down / series pull-up; A switches on their own inverter of inv (always enabled).
            mos('TERM_OR_'+leg+'_OUT_N',out,inv,'VSS','VSS',w=4.*g2)
            mos('TERM_OR_'+leg+'_OUT_NLS',out,'LS_SLOW','VSS','VSS',w=2.)
            mos('TERM_OR_'+leg+'_OUT_PLS','TERM_OR_'+leg+'_PLS','LS_SLOW','VDD','VDD','pfet_03v3',16.,.28)
            mos('TERM_OR_'+leg+'_OUT_P',out,inv,'TERM_OR_'+leg+'_PLS','VDD','pfet_03v3',16.,.28)
            mos('TERM_LSA_'+leg+'_GN','TERM_LSA_GATE_'+leg,inv,'VSS','VSS',w=4.)
            mos('TERM_LSA_'+leg+'_GP','TERM_LSA_GATE_'+leg,inv,'VDD','VDD','pfet_03v3',8.,.28)
            resistor('TERM_LSA_'+leg+'_BLEED','TERM_LSA_GATE_'+leg,'VSS',12500)
        else:
            mos('TERM_OR_'+leg+'_OUT_N',out,inv,'VSS','VSS',w=4.*g2)
            mos('TERM_OR_'+leg+'_OUT_P',out,inv,'VDD','VDD','pfet_03v3',8.*g2,.28)
        previous=out
        nb=lsm['term_bleed_segments'] if lsm else 4   # PD46: 12.5 kohm segments (PD44 POC: 100 kohm)
        for i in range(nb):
            following='VSS' if i==nb-1 else f'TERM_GATE_{leg}_BLEED_{i}'
            resistor(f'TERM_GATE_{leg}_BLEED_{i}',previous,following,12500)
            previous=following
        return out
    # Supply-powered, skewed inverter senses termination common mode. Its
    # analog trip range must be characterized; it is not a precision comparator.
    if hs_mirror_reference:
        mos('HS_REF','HS_PBIAS','HS_PBIAS','VDD','VDD','pfet_03v3',20.,1.)
    if ls_slow:
        mos('LS_SLOW_INV_N','LS_SLOW_B','LS_SLOW','VSS','VSS',w=2.)
        mos('LS_SLOW_INV_P','LS_SLOW_B','LS_SLOW','VDD','VDD','pfet_03v3',4.,.28)
    if lsm:   # PD46: LS limiter bias, mirrored from the HS reference (HS_PBIAS)
        mos('LS_BIAS_P','LSNB','HS_PBIAS','VDD','VDD','pfet_03v3',lsm['limit_p'][0],lsm['limit_p'][1])
        mos('LS_BIAS_N','LSNB','LSNB','VSS','VSS','nfet_03v3',lsm['limit_n'][0],lsm['limit_n'][1])
    mos('VCM_LOW_SENSE_N','VCM_LOW_OK','TERM_VCM','VSS','VSS',w=8.)
    mos('VCM_LOW_SENSE_P','VCM_LOW_OK','TERM_VCM','VDD','VDD','pfet_03v3',2.,.28)
    for leg in ('P','N'):
        pad='PAD_'+leg
        devices.extend(foundation_devices(leg))
        # Shared switched shunt: TERM_VCM selects ground for USB or a serial
        # common mode. The differential bridge reuses these physical resistors.
        local_enable=shared_low_enable(leg)
        if termination_geometry_um is None:
            resistor('TERM_'+leg,pad,'TERM_'+leg+'_R',24.,'ppolyf_s')
        else:
            # Parallel segments keep each primitive inside the 21 x 26 um placement grid.
            w_um, l_um, segments = termination_geometry_um
            for k in range(segments):
                devices.append(Resistor('TERM_'+leg+('' if segments == 1 else f'_SEG{k}'),(pad,'TERM_'+leg+'_R','VSS'),'ppolyf_u',w_um,l_um))
        for i in range(termination_switch_units):
            g=local_enable if not ls_slow or lsm or i>=ls_slow['low_a_units'] else 'TERM_LSA_GATE_'+leg   # PD28 LS: A switches
            mos(f'TERM_{leg}_{i}','TERM_'+leg+'_R',g,'TERM_VCM','VSS',N6[0],20.,N6[1])
        if termination_trim:
            tw, tl = termination_trim['poly']
            for k in range(termination_trim['bits']):
                node = f'TRIM_{leg}_{k}_R'
                devices.append(Resistor(f'TRIM_{leg}_{k}', (pad, node, 'VSS'), 'ppolyf_u', tw * 2 ** k, tl))
                total = termination_trim['switch_w'] * 2 ** k
                pieces = -(-total // 20)
                for j in range(int(pieces)):
                    mos(f'TRIM_{leg}_{k}_{j}', node, f'TERM_TRIM{k}', 'TERM_VCM', 'VSS', N6[0], total / pieces, N6[1])
        # Divider switch is on the low-voltage side of the upper resistor.
        # This avoids an NMOS pass-gate ceiling at the 3.3V bond input.
        resistor('DIV_TOP_'+leg,pad,'DIV_'+leg,blocks['rxlevel']['parameters']['series_r_ohm'])
        resistor('DIV_BOTTOM_'+leg,'DIV_'+leg,'DIV_LOW_'+leg,blocks['rxlevel']['parameters']['shunt_r_ohm'])
        mos('DIV_GROUND_'+leg,'DIV_LOW_'+leg,'DIV_ENABLE','VSS','VSS',N6[0],20.,N6[1])
        mos('DIV_SELECT_'+leg,'DIV_'+leg,'DIV_ENABLE','RX_'+leg,'VSS','nfet_06v0',20.,.7)
        for i in range(4):
            mos(f'BYPASS_{leg}_{i}',pad,'BYPASS_ENABLE','RX_'+leg,'VSS','nfet_06v0',20.,.7)
        # A current source per leg permits independent single-ended USB drive.
        for i in range(hs_units):
            current=f'HS_{leg}_{i}'
            mos(current+'_SOURCE',current,'HS_PBIAS','VDD','VDD','pfet_03v3',20.,1.)
            mos(current+'_ISOLATE',current,'HS_'+leg,pad,'VSS','nfet_06v0',20.,.7)
        if lsm:
            high_side('FS_'+leg,pad,'FS_HIGH_'+leg,15.8,fs_high_units,fs_high_width_um,fs_series_geometry_um)
            # Miller integrators (PD46): pad-side TG + MIM per driver
            well='FS_'+leg+'_WELL'
            for side,node,gate in (('H','FS_'+leg+'_OUT','FS_'+leg+'_GATE'),('L','TERM_'+leg+'_R','TERM_GATE_'+leg)):
                m=f'LSM_{side}_{leg}'
                mos(m+'_TGN',node,'LS_SLOW',m,'VSS','nfet_06v0',lsm['tg_w'],.7)
                mos(m+'_TGP',node,'LS_SLOW_B',m,well,'pfet_06v0',lsm['tg_w'],.55)
                devices.append(Capacitor(m+'_CAP',(m,gate),'cap_mim_2f0_m4m5_noshield',lsm['c_um'],lsm['c_um']))
        elif ls_slow:
            a=ls_slow['high_a_units'];b=fs_high_units-a
            high_side('FS_'+leg,pad,'FS_HIGH_'+leg,15.8,a,fs_high_width_um,fs_series_geometry_um)
            high_side('FS_'+leg+'B',pad,'FS_HIGH_'+leg,15.8,b,fs_high_width_um,None,control_gate='LS_SLOW_B',
                      share=('FS_'+leg+'_WELL','FS_'+leg+'_OUT'))
            # place the B units right after the A units (contiguous drain node, as in the canonical bank)
            units_b=[d for d in devices if d.name.startswith(('FS_'+leg+'B_SUP_','FS_'+leg+'B_PAD_'))]
            rest=[d for d in devices if d not in units_b]
            k=max(i for i,d in enumerate(rest) if d.name.startswith('FS_'+leg+'_PAD_'))+1
            devices[:]=rest[:k]+units_b+rest[k:]
        else:
            high_side('FS_'+leg,pad,'FS_HIGH_'+leg,15.8,fs_high_units,fs_high_width_um,fs_series_geometry_um)
        high_side('PULLUP_'+leg,pad,'PULLUP_'+leg,blocks['usbfs']['parameters']['pullup_ohm']-320,4)
        resistor('PULLDOWN_'+leg,pad,'PULLDOWN_'+leg+'_R',blocks['usbfs']['parameters']['pulldown_ohm']-800)
        mos('PULLDOWN_'+leg,'PULLDOWN_'+leg+'_R','PULLDOWN_'+leg,'VSS','VSS',N6[0],8.,N6[1])
    # Bridge the inner resistor nodes, reusing both pad-side termination
    # resistors. Ground/common-mode switches stay off in differential mode.
    # All branches remain attached in every configuration; no ideal switch
    # erases the off bridge's capacitance. Control exclusion remains local work.
    for i in range(differential_units):
        mos(f'DIFF_TERM_{i}','TERM_P_R','DIFF_ENABLE','TERM_N_R','VSS',N6[0],differential_width_um,N6[1])
    return Circuit('pad_wired_receive_usb',ports,devices,required,[
        'FS_LOW_P/N reuse the shunt bank through bias-qualified local CMOS controls. The nominal bias detector blocks lone FS-low requests at serial common mode; it does not ground TERM_VCM, override TERM_ENABLE, or enforce differential/FS exclusion. Trip variation and transient qualification remain open.',
        'RX_P/N connect to the shared serial receiver; USB differential/single-ended sensing attaches at PAD_P/N. Receivers are core boundaries.',
        'High-side gate pull-downs have supply-gated ground isolation; other control interlocks, reset/brownout supervision and break-before-make sequencing remain open.',
        'HS current bias, common-mode source, impedance trim, FS/LS slew control and termination mutual exclusion remain open.',
        'Back-to-back PMOS sources and bodies share floating wells; power-off and body stress must be checked with retained charge.',
        'Divider high-Z leakage and internal charge injection require measurements; no ideal switch removes inactive branch capacitance.',
        'All dimensions are first-pass candidates; no ESD or protocol compliance claim.',
    ])
