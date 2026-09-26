"""Candidate recovery register mailbox over the existing 32-clock SPI format.

Transaction-level model: the caller supplies the observed command/address/data
and number of clocks under CS. No electrical SPI or physical CDC qualification.
A single request bank is held until explicit reference-domain completion.
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

    def reference_edge(self):
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
