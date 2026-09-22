"""Continuous RX/TX through existing converters, clocks, queues and host framing."""
import copy,math
from internal_monitor_lifecycle import MonitorChip
from continuous_iq_codec import StreamEncoder,StreamDecoder

class ContinuousChip(MonitorChip):
    TILE_COMMANDS=MonitorChip.TILE_COMMANDS+('rx_stream_start','tx_stream_start','stream_start')
    def start_rx_stream(self,start):
        # Reuse common preflight, clock setup and return framing; no event runs
        # between initialization and selection of count-free packing.
        self.capture(1,start)
        self.adc_encoder=StreamEncoder(2*self.bits)
        self.host_decoder=StreamDecoder(2*self.bits)
        self.adc_left=math.inf
    def start_tx_stream(self,start):
        if self.playback_selected or self.decoder is not None or self.tx.queue:
            raise ValueError('Continuous host TX requires unowned empty DAC input')
        self.schedule(1,start)
        self.decoder=StreamDecoder(2*self.bits)
        self.remaining=math.inf
    def start_streams(self,flags,start):
        if flags not in (1,2,3):raise ValueError('Select TX, RX or both')
        # Scheduling allocates fresh clocks/codecs and scalar state only. Stage
        # both paths before publishing: neither can run during this operation.
        candidate=copy.copy(self)
        if flags&1:candidate.start_tx_stream(start)
        if flags&2:candidate.start_rx_stream(start+self.local_rx_offset_s)
        self.__dict__.update(candidate.__dict__)
    def execute_management(self,operation,payload,time):
        if operation=='stream_start':
            flags=payload&3;delay=payload>>2
            if not 1<=delay<=65535:raise ValueError('Invalid stream start delay')
            self.start_streams(flags,time+delay*self.control_period)
            return dict(value=flags)
        if operation not in ('rx_stream_start','tx_stream_start'):return super().execute_management(operation,payload,time)
        if not 1<=payload<=65535:raise ValueError('Stream start delay must fit16 bits and be positive')
        start=time+payload*self.control_period
        if operation=='rx_stream_start':self.start_rx_stream(start)
        else:self.start_tx_stream(start)
        return {}
