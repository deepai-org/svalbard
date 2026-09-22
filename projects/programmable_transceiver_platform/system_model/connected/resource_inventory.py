"""Discovery of implemented resource dependencies and current ownership.

IDs are model-management IDs, not a frozen hardware register ABI. Busy reflects
scheduled work or in-flight data; configuration ownership can persist while idle.
"""
RESOURCES=(
    ('iq_adc',('rf_rx_filter','rf_lo','sample_clock','adc_reference')),
    ('iq_dac',('rf_tx_filter','rf_lo','sample_clock','dac_reference')),
    ('capture_bank',('iq_adc',)),
    ('playback_bank',('iq_dac',)),
    ('wired_rx',('wired_cdr',)),
    ('wired_tx',('wired_tx_clock',)),
)
OWNERS=('none','rf_receive','host_stream','playback','capture','wired_receive','wired_transmit')


def resource_word(chip,index):
    if not isinstance(index,int) or not 0<=index<len(RESOURCES):
        raise ValueError('Unknown resource ID')
    # Downstream return framing can emit idle words forever; it does not own ADC.
    adc=bool(chip.adc_left or chip.adc_pending)
    dac=bool(chip.remaining or chip.tx.queue or chip.dac_pending)
    if index==0:owner=1;busy=adc
    elif index==1:owner=3 if chip.playback_selected else 2;busy=dac
    elif index==2:owner=4 if chip.capture_bank.enabled else 0;busy=bool(owner and adc and not chip.capture_bank.done)
    elif index==3:owner=3 if chip.playback_selected else 0;busy=bool(owner and dac)
    elif index==4:
        owner=5;rx=getattr(chip,'live_rx',None);busy=bool(rx and rx.enabled and not rx.done)
    else:
        owner=6;busy=bool(chip.wire_remaining or chip.wire_queue or (chip.serializer is not None and chip.serializer.active))
    # [7:0] owner, [8] busy, [9] armed/frozen, [10] enabled/assigned.
    return owner | (int(busy)<<8) | (int(chip.session.armed)<<9) | (int(owner!=0)<<10)
