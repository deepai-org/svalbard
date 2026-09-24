"""Candidate generic resource command payload; no protocol identifiers.

Pure codec for the existing 32-bit management payload. Register/RTL encoding and
canonical queue dispatch are separate integration obligations. Zero means the
legacy/default clock choice, not a physically zero-frequency clock.
"""
ENGINES=('none','wire','rf')
RATES=(None,480e6,1.25e9,1.5e9,1.62e9,2.5e9,.7425e9,1.485e9)
MASK=(1<<9)-1


def decode_resource_word(word):
    if type(word) is not int or not 0<=word<=MASK:
        raise ValueError('Reserved resource configuration bits or invalid payload')
    owner=word&3;rate=(word>>2)&7
    if owner>=len(ENGINES) or rate>=len(RATES):
        raise ValueError('Reserved resource field encoding')
    result=dict(engine=ENGINES[owner],line_rate_bps=RATES[rate],
        frame_words=8 if word&(1<<5) else 64,
        tx_enabled=bool(word&(1<<6)),rx_enabled=bool(word&(1<<7)),
        pad_path='bidirectional' if word&(1<<8) else 'serial')
    if result['engine']!='wire' and (rate or result['frame_words']!=64 or result['pad_path']!='serial'):
        raise ValueError('Wired resource fields without wired ownership')
    return result


def encode_resource_word(*,engine,line_rate_bps=None,frame_words=64,
                         tx_enabled=True,rx_enabled=True,pad_path='serial'):
    if (engine not in ENGINES or line_rate_bps not in RATES or
            frame_words not in (8,64) or pad_path not in ('serial','bidirectional') or
            type(tx_enabled) is not bool or type(rx_enabled) is not bool):
        raise ValueError('Unsupported resource configuration')
    word=(ENGINES.index(engine)|(RATES.index(line_rate_bps)<<2)|
          (int(frame_words==8)<<5)|(int(tx_enabled)<<6)|(int(rx_enabled)<<7)|
          (int(pad_path=='bidirectional')<<8))
    decode_resource_word(word)
    return word


class ResourceConfigurationCommands:
    """Dispatch adapter for the existing serialized-management apply callback.

    The owning composition must include RESOURCE_COMMANDS in TILE_COMMANDS.
    This adapter does not replace queue timing, epoch fences or chip permissions.
    """
    RESOURCE_COMMANDS=('configure_resources','record_return_configure','configure_wire_interface')

    def execute_management(self,operation,payload,time):
        if operation=='configure_wire_interface':
            if type(payload) is not int or not 0<=payload<=3:
                raise ValueError('Reserved wire-interface bits')
            forwarded=bool(payload&2)
            rate=getattr(self,'wire_rate_override',None)
            if forwarded and rate not in (.7425e9,1.485e9):
                raise ValueError('Unsupported forwarded word-reference rate')
            self.configure_wire_interface(
                electrical='dc_current_sink' if payload&1 else 'ac_differential',
                clock_source='forwarded_word' if forwarded else 'embedded',
                word_reference_hz=rate/10 if forwarded else None)
            return dict(value=payload)
        if operation=='record_return_configure':
            if type(payload) is not int or payload not in (0,1):raise ValueError('Reserved record-return control bits')
            self.configure_record_return(enabled=bool(payload))
            return dict(value=payload)
        if operation=='configure_resources':
            settings=decode_resource_word(payload)
            self.configure_resources(**settings)
            return dict(value=payload)
        return super().execute_management(operation,payload,time)


def validate_wire_timing(line_rate_bps, clock_source='embedded', reference_hz=None):
    """Behavioral tuning target; does not widen the legacy command encoding.

    Physical PLL/CDR tuning bands and reference input limits remain unqualified.
    Forwarded range stays within the two existing video endpoint targets.
    """
    import math
    if not math.isfinite(line_rate_bps) or not 480e6 <= line_rate_bps <= 2.5e9:
        raise ValueError('Wired rate outside candidate envelope')
    if clock_source not in ('embedded', 'forwarded_word'):
        raise ValueError('Unknown clock source')
    if clock_source == 'forwarded_word':
        if (reference_hz is None or not math.isfinite(reference_hz) or
                not 74.25e6/1.001 <= reference_hz <= 148.5e6 or
                not math.isclose(line_rate_bps, 10*reference_hz, rel_tol=1e-12)):
            raise ValueError('Forwarded clock must satisfy bounded x10 relationship')
    elif reference_hz is not None:
        raise ValueError('Embedded timing does not specify a forwarded reference')
    return dict(line_rate_bps=line_rate_bps, clock_source=clock_source,
                word_reference_hz=reference_hz)


def validate_rf_settings(sample_hz=40e6, tx_cutoff_hz=20e6,
                         rx_cutoff_hz=9.157407e6, rx_gain=1., rx_filter_order=1, converter_bits=12):
    """Generic candidate filter-bank/divider settings, not protocol selectors.

    Sample divisors reuse 40 MHz; 8/12-bit precision is independent of rate.
    Cutoffs are one-sided analog poles, not occupied channel bandwidths.
    """
    import math
    if type(rx_filter_order) is not int or rx_filter_order not in (1,5):
        raise ValueError('Supported filter reductions are first and fifth order')
    if type(converter_bits) is not int or converter_bits not in (8,12):
        raise ValueError('Converter precision must be 8 or 12 bits')
    values=(sample_hz,tx_cutoff_hz,rx_cutoff_hz,rx_gain)
    if not all(math.isfinite(v) and v>0 for v in values):
        raise ValueError('Positive finite RF settings required')
    if sample_hz not in (5e6,10e6,20e6,40e6):
        raise ValueError('Unsupported reference divider')
    if not (.1e6<=rx_cutoff_hz<=9.157407e6 and .1e6<=tx_cutoff_hz<=20e6
            and max(tx_cutoff_hz,rx_cutoff_hz)<=sample_hz/2 and .5<=rx_gain<=2.):
        raise ValueError('RF setting outside candidate envelope')
    return dict(sample_hz=sample_hz,tx_cutoff_hz=tx_cutoff_hz,
                rx_cutoff_hz=rx_cutoff_hz,rx_gain=rx_gain,rx_filter_order=rx_filter_order,converter_bits=converter_bits)
