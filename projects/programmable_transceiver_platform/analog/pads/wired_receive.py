"""Shared RX/USB pad candidate; analog front ends attach at explicit ports.

All branches remain physically connected. Controls are voltages supplied by the
core, not protocol names. Dimensions are candidate sizes, not achieved specs.
"""
import json
from circuits import Circuit, Mos, Resistor, foundation_devices
from design import PROJECT, resolve


def build(*, hs_units=14, fs_high_units=24, differential_units=5, differential_width_um=20., fs_high_width_um=20., fs_series_geometry_um=None):
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
    def mos(name,d,g,s,b,model='nfet_03v3',w=8.,l=.28):
        devices.append(Mos(name,(d,g,s,b),model,w,l))
    def resistor(name,a,b,ohm,model='ppolyf_u_1k',width=1.):
        sheet=1000 if model=='ppolyf_u_1k' else 7.3
        devices.append(Resistor(name,(a,b,'VSS'),model,width,round(ohm/sheet*width,2)))
    def high_side(name,destination,enable,resistance,units,width=20.,series_geometry=None):
        # Back-to-back PMOS with a common floating source/well. Each drain
        # faces a different endpoint, so neither body diode alone backfeeds
        # VDD. Passive gate-to-source bias keeps the pair off without power.
        well=name+'_WELL';gate=name+'_GATE';out=name+'_OUT'
        for i in range(units):
            mos(f'{name}_SUP_{i}','VDD',gate,well,well,'pfet_03v3',width,.28)
            mos(f'{name}_PAD_{i}',out,gate,well,well,'pfet_03v3',width,.28)
        # Series ground switch opens when the local supply disappears, even
        # if the external enable remains asserted. No ideal power-good signal.
        # The floating gate can undershoot during VDD collapse while a
        # retained request remains high; use the 6V gate-oxide device here.
        mos(name+'_CONTROL',gate,enable,name+'_CONTROL_S','VSS','nfet_06v0',2.,.7)
        mos(name+'_POWER',name+'_CONTROL_S','VDD','VSS','VSS',w=4.)
        # A falling VDD turns on a well-referenced PMOS that restores the
        # pass gates toward their floating source, avoiding a resistor-only
        # 100kohm discharge delay. Its body follows the same local well.
        mos(name+'_RESTORE',gate,'VDD',well,well,'pfet_03v3',4.,.28)
        previous=well
        for i in range(8):
            following=gate if i==7 else f'{name}_BLEED_{i}'
            resistor(f'{name}_BLEED_{i}',previous,following,12500)
            previous=following
        if series_geometry is None:
            resistor(name+'_R',out,destination,resistance,'ppolyf_s' if resistance<100 else 'ppolyf_u_1k')
        else:
            devices.append(Resistor(name+'_R',(out,destination,'VSS'),'ppolyf_s',*series_geometry))
    def shared_low_enable(leg):
        # Static CMOS complex gate: TERM_ENABLE OR (FS_LOW AND VCM_LOW_OK).
        # Bias qualification blocks a lone FS-low request at serial common
        # mode; TERM_ENABLE remains a distinct intentional shunt request.
        low='FS_LOW_'+leg;inv='TERM_OR_'+leg+'_B';out='TERM_GATE_'+leg;series='TERM_OR_'+leg+'_S'
        mos('TERM_OR_'+leg+'_N0',inv,'TERM_ENABLE','VSS','VSS',w=2.)
        mos('TERM_OR_'+leg+'_N1',inv,low,'TERM_OR_'+leg+'_NS','VSS',w=2.)
        mos('TERM_OR_'+leg+'_QUAL_N','TERM_OR_'+leg+'_NS','VCM_LOW_OK','VSS','VSS',w=4.)
        mos('TERM_OR_'+leg+'_P0',series,'TERM_ENABLE','VDD','VDD','pfet_03v3',4.,.28)
        mos('TERM_OR_'+leg+'_P1',inv,low,series,'VDD','pfet_03v3',4.,.28)
        mos('TERM_OR_'+leg+'_QUAL_P',inv,'VCM_LOW_OK',series,'VDD','pfet_03v3',4.,.28)
        mos('TERM_OR_'+leg+'_OUT_N',out,inv,'VSS','VSS',w=4.)
        mos('TERM_OR_'+leg+'_OUT_P',out,inv,'VDD','VDD','pfet_03v3',8.,.28)
        previous=out
        for i in range(4):
            following='VSS' if i==3 else f'TERM_GATE_{leg}_BLEED_{i}'
            resistor(f'TERM_GATE_{leg}_BLEED_{i}',previous,following,12500)
            previous=following
        return out
    # Supply-powered, skewed inverter senses termination common mode. Its
    # analog trip range must be characterized; it is not a precision comparator.
    mos('VCM_LOW_SENSE_N','VCM_LOW_OK','TERM_VCM','VSS','VSS',w=8.)
    mos('VCM_LOW_SENSE_P','VCM_LOW_OK','TERM_VCM','VDD','VDD','pfet_03v3',2.,.28)
    for leg in ('P','N'):
        pad='PAD_'+leg
        devices.extend(foundation_devices(leg))
        # Shared switched shunt: TERM_VCM selects ground for USB or a serial
        # common mode. The differential bridge reuses these physical resistors.
        local_enable=shared_low_enable(leg)
        resistor('TERM_'+leg,pad,'TERM_'+leg+'_R',24.,'ppolyf_s')
        for i in range(8):
            mos(f'TERM_{leg}_{i}','TERM_'+leg+'_R',local_enable,'TERM_VCM','VSS',w=20.)
        # Divider switch is on the low-voltage side of the upper resistor.
        # This avoids an NMOS pass-gate ceiling at the 3.3V bond input.
        resistor('DIV_TOP_'+leg,pad,'DIV_'+leg,blocks['rxlevel']['parameters']['series_r_ohm'])
        resistor('DIV_BOTTOM_'+leg,'DIV_'+leg,'DIV_LOW_'+leg,blocks['rxlevel']['parameters']['shunt_r_ohm'])
        mos('DIV_GROUND_'+leg,'DIV_LOW_'+leg,'DIV_ENABLE','VSS','VSS',w=20.)
        mos('DIV_SELECT_'+leg,'DIV_'+leg,'DIV_ENABLE','RX_'+leg,'VSS','nfet_06v0',20.,.7)
        for i in range(4):
            mos(f'BYPASS_{leg}_{i}',pad,'BYPASS_ENABLE','RX_'+leg,'VSS','nfet_06v0',20.,.7)
        # A current source per leg permits independent single-ended USB drive.
        for i in range(hs_units):
            current=f'HS_{leg}_{i}'
            mos(current+'_SOURCE',current,'HS_PBIAS','VDD','VDD','pfet_03v3',20.,1.)
            mos(current+'_ISOLATE',current,'HS_'+leg,pad,'VSS','nfet_06v0',20.,.7)
        high_side('FS_'+leg,pad,'FS_HIGH_'+leg,15.8,fs_high_units,fs_high_width_um,fs_series_geometry_um)
        high_side('PULLUP_'+leg,pad,'PULLUP_'+leg,blocks['usbfs']['parameters']['pullup_ohm']-320,4)
        resistor('PULLDOWN_'+leg,pad,'PULLDOWN_'+leg+'_R',blocks['usbfs']['parameters']['pulldown_ohm']-800)
        mos('PULLDOWN_'+leg,'PULLDOWN_'+leg+'_R','PULLDOWN_'+leg,'VSS','VSS')
    # Bridge the inner resistor nodes, reusing both pad-side termination
    # resistors. Ground/common-mode switches stay off in differential mode.
    # All branches remain attached in every configuration; no ideal switch
    # erases the off bridge's capacitance. Control exclusion remains local work.
    for i in range(differential_units):
        mos(f'DIFF_TERM_{i}','TERM_P_R','DIFF_ENABLE','TERM_N_R','VSS',w=differential_width_um)
    return Circuit('pad_wired_receive_usb',ports,devices,required,[
        'FS_LOW_P/N reuse the shunt bank through bias-qualified local CMOS controls. The nominal bias detector blocks lone FS-low requests at serial common mode; it does not ground TERM_VCM, override TERM_ENABLE, or enforce differential/FS exclusion. Trip variation and transient qualification remain open.',
        'RX_P/N connect to the shared serial receiver; USB differential/single-ended sensing attaches at PAD_P/N. Receivers are core boundaries.',
        'High-side gate pull-downs have supply-gated ground isolation; other control interlocks, reset/brownout supervision and break-before-make sequencing remain open.',
        'HS current bias, common-mode source, impedance trim, FS/LS slew control and termination mutual exclusion remain open.',
        'Back-to-back PMOS sources and bodies share floating wells; power-off and body stress must be checked with retained charge.',
        'Divider high-Z leakage and internal charge injection require measurements; no ideal switch removes inactive branch capacitance.',
        'All dimensions are first-pass candidates; no ESD or protocol compliance claim.',
    ])
