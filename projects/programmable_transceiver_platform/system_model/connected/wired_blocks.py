"""Stateful NRZ serializer and one-pole channel, prescribed mid-bit sampling."""
import math

class WiredChannel:
    def __init__(self, rate_bps, bandwidth_ratio=1,swing=1.,postcursor=0.):
        if not all(math.isfinite(v) for v in (rate_bps,bandwidth_ratio,swing,postcursor)) or rate_bps<=0 or bandwidth_ratio<=0 or swing<=0 or not 0<=postcursor<1:
            raise ValueError('Invalid wired channel/driver parameters')
        self.swing=swing;self.postcursor=postcursor;self.previous_symbol=0.;self.peak_drive=0.
        self.rate=rate_bps
        self.decay=math.exp(-2*math.pi*bandwidth_ratio)
        self.state=0.
        self.bits=self.errors=0
        self.minimum_margin=float('inf')
    def word(self, value):
        result=0
        for bit in range(10):
            symbol=1 if value & (1 << bit) else -1
            drive=self.swing*(symbol-self.postcursor*self.previous_symbol)/(1+self.postcursor)
            self.previous_symbol=symbol;self.peak_drive=max(self.peak_drive,abs(drive))
            sampled=drive+(self.state-drive)*math.sqrt(self.decay)
            self.state=drive+(self.state-drive)*self.decay
            result |= int(sampled>0) << bit
            margin=sampled*symbol
            self.minimum_margin=min(self.minimum_margin,margin)
            self.errors+=int(margin<=0)
            self.bits+=1
        return result
    def report(self):
        return dict(swing=self.swing,postcursor=self.postcursor,peak_drive=self.peak_drive,bits=self.bits,observed_bit_errors=self.errors,
                    minimum_signed_margin=self.minimum_margin,
                    clock='prescribed mid-bit phase; no CDR')

def controls():
    a=WiredChannel(1e9)
    assert a.word(1023)==1023
    assert abs(a.state-(1-math.exp(-20*math.pi)))<1e-14
    b=WiredChannel(1e9)
    assert b.word(0)==0 and abs(a.state+b.state)<1e-14
    slow=WiredChannel(1e9,.03)
    for _ in range(20):slow.word(0x155)
    assert slow.errors>0


class CurrentSwitchChannel(WiredChannel):
    """Normalized differential current-switch/terminated-RC candidate.

    Unit drive represents 8 mA into 50 ohms (0.4 V differential). This shares
    serializer accounting, both pin voltages and current-sink compliance status.
    Outside compliance the ideal-current solution is flagged invalid, not clipped.
    """
    def __init__(self,rate_bps,*,switch_tau_s=100e-12,load_tau_s=100e-12,
                 termination_v=3.3,termination_ohm=50.,tail_current_a=.008,
                 minimum_sink_v=.4):
        if not all(math.isfinite(x) and x>0 for x in (switch_tau_s,load_tau_s)):
            raise ValueError('Positive finite switch/load time constants required')
        super().__init__(rate_bps,bandwidth_ratio=1/(2*math.pi*load_tau_s*rate_bps))
        self.switch_tau_s=switch_tau_s;self.load_tau_s=load_tau_s
        if not all(math.isfinite(x) and x>0 for x in (termination_v,termination_ohm,tail_current_a,minimum_sink_v)):
            raise ValueError('Positive finite pad electrical assumptions required')
        self.termination_v=termination_v;self.termination_ohm=termination_ohm
        self.tail_current_a=tail_current_a;self.minimum_sink_v=minimum_sink_v
        self.current_state=0.;self.volts_per_unit=termination_ohm*tail_current_a
        self.tail_state=0.;self.common_drop_state=0.
    def advance_state(self,drive,dt):
        if not math.isfinite(dt) or dt<0 or not math.isfinite(drive) or abs(drive)>1:
            raise ValueError('Invalid pad interval or current command')
        a=self.switch_tau_s;b=self.load_tau_s
        ea=math.exp(-dt/a);eb=math.exp(-dt/b)
        kernel=(dt/b)*eb if abs(a-b)<1e-8*b else a/(a-b)*(ea-eb)
        self.state=drive+(self.state-drive)*eb+(self.current_state-drive)*kernel
        self.current_state=drive+(self.current_state-drive)*ea
        target=abs(drive)
        self.common_drop_state=target+(self.common_drop_state-target)*eb+(self.tail_state-target)*kernel
        self.tail_state=target+(self.tail_state-target)*ea
    def pin_state(self,ground_v=0.):
        if not math.isfinite(ground_v):raise ValueError("Finite local ground required")
        common=self.termination_v-.5*self.volts_per_unit*self.common_drop_state
        vp=common+.5*self.volts_per_unit*self.state
        vn=common-.5*self.volts_per_unit*self.state
        ip=.5*self.tail_current_a*(self.tail_state-self.current_state)
        inn=.5*self.tail_current_a*(self.tail_state+self.current_state)
        valid=all(v-ground_v>=self.minimum_sink_v or i<=1e-15 for v,i in ((vp,ip),(vn,inn)))
        return dict(positive_v=vp,negative_v=vn,common_mode_v=common,
            positive_sink_a=ip,negative_sink_a=inn,current_compliance_valid=valid,
            termination_source_power_w=self.termination_v*(2*self.termination_v-vp-vn)/self.termination_ohm,
            resistor_power_w=((self.termination_v-vp)**2+(self.termination_v-vn)**2)/self.termination_ohm,
            sink_terminal_power_w=vp*ip+vn*inn,ground_transfer_power_w=ground_v*(ip+inn),
            sink_power_w=(vp-ground_v)*ip+(vn-ground_v)*inn)
    def word(self,value):
        # Keep the untimed word helper consistent with event-driven serialization.
        result=0
        for bit in range(10):
            symbol=1 if value&(1<<bit) else -1
            self.advance_state(symbol,.5/self.rate)
            margin=self.state*symbol;self.minimum_margin=min(self.minimum_margin,margin)
            self.bits+=1;self.errors+=int(margin<=0);result|=int(self.state>0)<<bit
            self.advance_state(symbol,.5/self.rate)
            self.previous_symbol=symbol;self.peak_drive=max(self.peak_drive,1.)
        return result
