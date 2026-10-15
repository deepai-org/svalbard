"""Scheduled-control requirements; timing arithmetic, not analog settling."""
from dataclasses import dataclass


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('invalid integer timing value')
    return value


@dataclass(frozen=True)
class TrimAction:
    current_code: int
    postcursor_code: int
    apply_word: int
    settled_word: int
    epoch: int


def plan_wire_trim(architecture, active, changes, *, requested_ui, now_ui,
                   epoch, active_epoch, training_window, fault=False):
    """Atomic current/postcursor change without STOP, idle insertion or clock reset."""
    _integer(now_ui); _integer(requested_ui)
    if fault or not training_window or epoch != active_epoch or requested_ui < now_ui:
        raise ValueError('unsafe, stale or late live trim')
    policy=architecture['control_semantics']['live_analog_updates']['wiredtx.config']
    if not changes or set(changes)-set(policy['allowed_fields']):
        raise ValueError('field is not live-adjustable')
    fields=architecture['control_fields']['wiredtx.config']['fields']
    selected={key: active[key] for key in policy['allowed_fields']}
    selected.update(changes)
    for key,value in selected.items():
        if type(value) is not int or not fields[key]['minimum'] <= value <= fields[key]['maximum']:
            raise ValueError('trim out of range')
    ratio=architecture['blocks']['clocktree']['parameters']['serializer_ratio']
    guard=architecture['control_fields']['digital.guard_config']['fields']['wire_trim_settle_ui']['default']
    apply_word=(requested_ui+ratio-1)//ratio
    settled_word=(apply_word*ratio+guard+ratio-1)//ratio
    return TrimAction(selected['current_code'],selected['postcursor_code'],
                      apply_word,settled_word,epoch)


@dataclass(frozen=True)
class DirectionAction:
    gate_tick: int
    ready_tick: int
    launch_tick: int
    epoch: int


def plan_rf_direction(architecture, *, direction, gate_tick, launch_tick,
                      now_tick, epoch, active_epoch, startup_ready,
                      clocks_alive, payload_ready, fault=False,
                      guard_ticks=None, additional_settling_ticks=0):
    """Require warm readiness; never hide a cold start or silently move a deadline."""
    for value in (gate_tick,launch_tick,now_tick,additional_settling_ticks):_integer(value)
    if direction not in ('rx_to_tx','tx_to_rx'):
        raise ValueError('invalid direction')
    if (fault or not startup_ready or not clocks_alive or not payload_ready
            or epoch != active_epoch or gate_tick < now_tick):
        raise ValueError('direction change not ready')
    field=architecture['control_fields']['digital.guard_config']['fields'][direction+'_ticks']
    guard=field['default'] if guard_ticks is None else guard_ticks
    if type(guard) is not int or not field['minimum']<=guard<=field['maximum']:
        raise ValueError('invalid direction guard')
    ready=gate_tick+guard+additional_settling_ticks
    if launch_tick < ready:
        raise ValueError('launch deadline precedes settling')
    return DirectionAction(gate_tick,ready,launch_tick,epoch)
