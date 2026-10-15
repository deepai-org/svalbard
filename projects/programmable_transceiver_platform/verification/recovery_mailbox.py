"""Candidate recovery register mailbox over the existing 32-clock SPI format.

Transaction-level model: the caller supplies the observed command/address/data
and number of clocks under CS. No electrical SPI or physical CDC qualification.
A single request bank is held until explicit management-domain completion.
The independent management oscillator, not REF_IN or either host clock,
advances request acceptance. Target-domain reset release may still wait for
its own clock; a stopped target must not block management status or isolation.
"""

class RecoveryMailbox:
    EPOCH=0x30
    TAG=0x31
    COMMIT=0x32
    REPLY_TAG=0x34
    REPLY_EPOCH=0x35
    REPLY_STATUS=0x36
    # Result: 0=success, 1=stale epoch, 2=illegal state, 3=timeout.
    # Bit 15 marks valid; bit 14 marks pending (no valid response yet).
    def __init__(self):
        self.shadow={};self.pending=None;self.visible=None;self.delay=0
        self.reply=None;self.last_request=None;self.error=None
        self.reply_pending=None;self.reply_delay=0

    def write(self,address,value,clocks=32,command=0x80):
        if type(clocks) is not int or clocks<0:raise ValueError('SPI clock count')
        if not 0<=value<65536:raise ValueError('Register width')
        if clocks<32 or command!=0x80:return False
        # Match pt_spi: commit on clock 32; extra clocks do not repeat a write.
        if address not in (self.EPOCH,self.TAG,self.COMMIT):return False
        if self.pending is not None:
            self.error='Mailbox busy';return False
        if address!=self.COMMIT:
            self.shadow[address]=value;return True
        if value==0:
            # Abandon only uncommitted fields. A pending action is never
            # cancelled ambiguously; the busy check above protects it.
            self.shadow.clear();self.error=None;return True
        if value not in (1,2,3) or set(self.shadow)!={self.EPOCH,self.TAG}:
            self.error='Incomplete or invalid recovery request';return False
        request=(self.shadow[self.TAG],self.shadow[self.EPOCH],value)
        self.shadow.clear()
        if self.last_request is not None and request[0]==self.last_request[0]:
            if request!=self.last_request:
                self.error='Request tag reused with different fields';return False
            return True  # Idempotent replay of retained response, no new action.
        self.last_request=request;self.pending=request;self.visible=None
        self.reply=None;self.delay=2;self.error=None
        return True

    def management_edge(self):
        if self.pending is not None and self.delay:
            self.delay-=1
            if not self.delay:
                self.visible=self.pending
                return self.visible
        return None

    def complete(self,tag,epoch,result):
        if self.visible is None or self.visible[0]!=tag:
            raise ValueError('Completion must match visible request')
        if type(epoch) is not int or not 0<=epoch<65536 or result not in (0,1,2,3):
            raise ValueError('Reply encoding')
        # Hold response data while publication crosses back to SCLK.
        self.reply_pending=(tag,epoch,result);self.reply_delay=2;self.visible=None

    def spi_edge(self):
        if self.reply_delay:
            self.reply_delay-=1
            if not self.reply_delay:
                self.reply=self.reply_pending;self.reply_pending=None;self.pending=None

    def read(self,address):
        if address==self.REPLY_STATUS:
            return 0x4000 if self.pending is not None else (0 if self.reply is None else 0x8000|self.reply[2])
        if self.reply is None:return 0
        if address==self.REPLY_TAG:return self.reply[0]
        if address==self.REPLY_EPOCH:return self.reply[1]
        return 0


def fault_notification_budget(*, line_rate_bps, spi_hz, poll_start_interval_s,
                              detection_s, publication_s, host_service_s):
    """Conditional SPI polling bound; payload quarantine resides in the FPGA.

    publication_s includes a persistent fault becoming safely readable. Poll
    spacing is a maximum start-to-start interval including bus contention.
    The next complete read is used, avoiding reliance on an in-flight snapshot.
    """
    import math
    if not all(math.isfinite(v) and v>0 for v in
               (line_rate_bps,spi_hz,poll_start_interval_s)):
        raise ValueError('Positive finite rates and bounded polling required')
    if not all(math.isfinite(v) and v>=0 for v in
               (detection_s,publication_s,host_service_s)):
        raise ValueError('Finite nonnegative latency bounds required')
    transaction_s=32/spi_hz
    if poll_start_interval_s<transaction_s:
        raise ValueError('Polling interval overlaps SPI transactions')
    latency=detection_s+publication_s+poll_start_interval_s+transaction_s+host_service_s
    return dict(notification_bound_s=latency,transaction_s=transaction_s,
        fpga_quarantine_bytes=math.ceil(line_rate_bps*latency/8),
        additional_chip_payload_storage_bytes=0,
        scope='Conditional bound from supplied deadlines, not measured timing or implemented fault transport. Quarantine covers a raw serial-data-rate stream; round up further for FPGA words/metadata and retain protocol context separately. No credit for CRC detection, in-flight reads or stopped-clock watchdog. Unbounded bus/host service gives no finite guarantee.')


class StickyFaultPublication:
    """Behavioral first-fault latch in a surviving management domain.

    Abstract status snapshot, not an adopted SPI register encoding. Publication
    delay includes CDC; no recovered-clock edges are required after capture.
    Epochs are logical model epochs, not a finite-width wraparound protocol.
    """
    def __init__(self, publication_s):
        import math
        if not math.isfinite(publication_s) or publication_s<0:
            raise ValueError('Finite nonnegative publication delay required')
        self.publication_s=publication_s;self.pending=None;self.observed=False
        self.time_s=0.

    def _advance(self,time_s):
        import math
        if not math.isfinite(time_s) or time_s<self.time_s:
            raise ValueError('Monotonic finite management time required')
        self.time_s=time_s

    def capture(self,time_s,epoch,cause):
        self._advance(time_s)
        if type(epoch) is not int or epoch<0 or not isinstance(cause,str) or not cause:
            raise ValueError('Fault epoch and cause required')
        if self.pending is None:
            self.pending=(epoch,cause,time_s+self.publication_s)
            self.observed=False

    def snapshot(self,time_s):
        self._advance(time_s)
        if self.pending is None or time_s<self.pending[2]:return None
        self.observed=True
        return self.pending[:2]

    def acknowledge_stop(self,time_s,*,stopped_epoch,new_epoch):
        self._advance(time_s)
        if (self.pending is None or not self.observed or stopped_epoch!=self.pending[0]
                or type(new_epoch) is not int or new_epoch<=stopped_epoch):
            raise ValueError('Observed matching fault and completed new-epoch STOP required')
        self.pending=None;self.observed=False
