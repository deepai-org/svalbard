"""Candidate lifecycle contract; readiness inputs are not physical lock detectors."""
class Session:
    def __init__(self):
        self.reset()
    def reset(self):
        self.mode=None;self.armed=False;self.host_ready=False
        self.ready={'rf':False,'wire':False};self.fault={'rf':False,'wire':False}
    def configure(self,mode):
        if self.armed:raise ValueError('Mode frozen while armed; reset required')
        if mode not in (0,1):raise ValueError('Unsupported mode')
        self.mode=mode
    def arm(self):
        if self.mode is None or not self.host_ready:raise ValueError('Configuration and host readiness required')
        self.armed=True
    def enabled(self,engine):
        return self.armed and self.host_ready and self.ready[engine] and not self.fault[engine]
    def trip(self,engine):
        self.fault[engine]=True;self.ready[engine]=False
    def reset_engine(self,engine):
        self.fault[engine]=False;self.ready[engine]=False

def controls():
    s=Session()
    try:s.arm()
    except ValueError:pass
    else:raise AssertionError('Unconfigured arm accepted')
    s.configure(0);s.host_ready=True;s.arm()
    assert not s.enabled('rf') and not s.enabled('wire')
    s.ready.update(rf=True,wire=True)
    try:s.configure(1)
    except ValueError:pass
    else:raise AssertionError('Live mode change accepted')
    s.trip('wire');assert s.enabled('rf') and not s.enabled('wire')
    s.ready['wire']=True;assert not s.enabled('wire')  # Fault remains latched.
    s.reset_engine('wire');assert not s.enabled('wire') and s.enabled('rf')
    s.ready['wire']=True;assert s.enabled('wire')
    s.reset();s.configure(1)
    assert not s.armed and not s.host_ready and not any(s.ready.values())
