"""Generic RX validity policy; phase/quiet observations come from analog models.

This is a control-state requirement model, not a simulation of CDR acquisition.
No protocol decoding and no analog-performance claim are made here.
Callers supply every transition/quiet change in time order; sparse observations
cannot stand in for an omitted active bitstream.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Observation:
    state: str
    valid: bool
    fault: str | None
    acquisition_failed: bool = False


class ReceiveQualification:
    def __init__(self, *, ui_s, holdover_ui=64, acquisition_ui=1024,
                 quiet_source='none', acquisition_failure='fault',count_recovered_edges=False):
        if not math.isfinite(ui_s) or ui_s <= 0:
            raise ValueError('positive finite UI required')
        if type(holdover_ui) is not int or not 1 <= holdover_ui < 1<<16:
            raise ValueError('Holdover UI count outside16bit range')
        if type(acquisition_ui) is not int or not 1 <= acquisition_ui < 1<<24:
            raise ValueError('Acquisition UI count outside24bit range')
        if quiet_source not in ('none', 'electrical_quiet', 'squelch', 'scheduled'):
            raise ValueError('invalid quiet source')
        if acquisition_failure not in ('fault', 'report_drop'):
            raise ValueError('invalid acquisition-failure policy')
        if type(count_recovered_edges) is not bool:raise ValueError("Boolean recovered-edge mode required")
        self.count_recovered_edges=count_recovered_edges
        self.holdover_ui=holdover_ui;self.acquisition_ui=acquisition_ui
        self.last_edge_count=None;self.last_good_edge_count=None;self.started_edge_count=None
        self.ui_s = ui_s
        self.holdover_s = holdover_ui * ui_s
        self.acquisition_s = acquisition_ui * ui_s
        self.quiet_source = quiet_source
        self.failure_policy = acquisition_failure
        self.state = 'disabled'
        self.fault = None
        self.last_time = -math.inf
        self.last_good = None
        self.started = None
        self.quiet_until = -math.inf

    def schedule_quiet(self, now_s, duration_ui, maximum_ui):
        if self.quiet_source != 'scheduled':
            raise ValueError('scheduled quiet is not selected')
        if not math.isfinite(now_s) or now_s < self.last_time:
            raise ValueError('time must be monotonic')
        if (type(duration_ui) is not int or type(maximum_ui) is not int
                or not 1 <= duration_ui <= maximum_ui <= 2**24-1):
            raise ValueError('quiet interval exceeds explicit bound')
        if now_s < self.quiet_until:
            raise ValueError('cannot extend an active quiet interval')
        self.quiet_until = now_s + duration_ui * self.ui_s

    def observe(self, now_s, *, enabled=True, local_tx=False,
                electrical_quiet=False, squelch=False, transition=False,
                phase_qualified=False, clock_ok=True, supply_ok=True,recovered_edge_count=None):
        if not math.isfinite(now_s) or now_s < self.last_time:
            raise ValueError('time must be monotonic')
        if self.count_recovered_edges:
            if (type(recovered_edge_count) is not int or recovered_edge_count<0 or
                    (self.last_edge_count is not None and recovered_edge_count<self.last_edge_count)):
                raise ValueError('Monotonic recovered edge count required')
        elif recovered_edge_count is not None:raise ValueError('Recovered-edge mode is not selected')
        self.last_time = now_s
        self.last_edge_count=recovered_edge_count
        def expired():
            return (recovered_edge_count-self.last_good_edge_count>self.holdover_ui
                    if self.count_recovered_edges else now_s-self.last_good>self.holdover_s)
        # Supply/reference failures are never hidden by packet gaps or local TX.
        if not clock_ok or not supply_ok:
            self.fault = 'clock' if not clock_ok else 'supply'
        if (self.fault is None and self.state in ('tracking', 'holdover')
                and expired()):
            self.fault = 'unexpected_rx_loss'
        if self.fault:
            self.state = 'fault'
            return Observation(self.state, False, self.fault)
        if not enabled or local_tx:
            self.state = 'disabled'
            self.started = self.last_good = None
            return Observation(self.state, False, None)
        quiet = ((self.quiet_source == 'electrical_quiet' and electrical_quiet)
                 or (self.quiet_source == 'squelch' and squelch)
                 or (self.quiet_source == 'scheduled' and now_s < self.quiet_until))
        if quiet:
            self.state = 'quiet'
            self.started = self.last_good = None
            return Observation(self.state, False, None)
        if self.state == 'drop_burst':
            return Observation(self.state, False, None)
        if self.state in ('disabled', 'quiet'):
            self.state, self.started = 'acquiring', now_s
            self.started_edge_count=recovered_edge_count
        if self.state == 'acquiring':
            if (recovered_edge_count-self.started_edge_count>=self.acquisition_ui if self.count_recovered_edges else now_s-self.started>=self.acquisition_s):
                if self.failure_policy == 'report_drop':
                    self.state = 'drop_burst'
                    return Observation(self.state, False, None, True)
                self.state, self.fault = 'fault', 'acquisition_timeout'
                return Observation(self.state, False, self.fault, True)
            elif phase_qualified and transition:
                self.state, self.last_good = 'tracking', now_s
                self.last_good_edge_count=recovered_edge_count
            else:
                return Observation(self.state, False, None)
        elif transition and phase_qualified:
            self.state, self.last_good = 'tracking', now_s
            self.last_good_edge_count=recovered_edge_count
        elif expired():
            self.state, self.fault = 'fault', 'unexpected_rx_loss'
        else:
            self.state = 'holdover'
        return Observation(self.state,
                           self.fault is None and phase_qualified,
                           self.fault)


def holdover_phase_bound(*, run_ui, residual_ppm, initial_error_ui,
                         uncertainty_ui, available_ui):
    """Conservative phase budget. A longer timeout cannot repair excessive drift."""
    if type(run_ui) is not int or not 1 <= run_ui <= 65535:
        raise ValueError('run outside holdover counter range')
    values=(residual_ppm,initial_error_ui,uncertainty_ui,available_ui)
    if not all(math.isfinite(x) and x >= 0 for x in values) or not 0 < available_ui < .5:
        raise ValueError('invalid phase budget')
    bound=initial_error_ui+run_ui*residual_ppm*1e-6+uncertainty_ui
    return {'bound_ui':bound,'margin_ui':available_ui-bound,
            'admissible':bound < available_ui}


def modulated_holdover_phase_bound(*, segments, initial_error_ui,
                                   uncertainty_ui, available_ui):
    """Bound a transition-free gap with piecewise-linear residual frequency.

    Each segment is (duration_ui, starting_ppm, ending_ppm). Frequency is
    incoming minus recovered, AFTER loop tracking; source SSC is not residual
    error. Check interior extrema as well as endpoints: zero net drift can
    still cross the eye during the gap. This accepts a supplied loop response,
    and does not synthesize or qualify that response.
    """
    values = (initial_error_ui, uncertainty_ui, available_ui)
    if (not all(math.isfinite(x) and x >= 0 for x in values)
            or not 0 < available_ui < .5):
        raise ValueError('invalid phase budget')
    segments = tuple(segments)
    if not segments:
        raise ValueError('a nonempty frequency trajectory is required')
    phase = peak = duration = 0.
    for width, start, end in segments:
        if not all(math.isfinite(x) for x in (width, start, end)) or width <= 0:
            raise ValueError('finite frequency and positive duration required')
        duration += width
        if duration > 65535:
            raise ValueError('gap exceeds holdover counter range')
        slope = (end - start) / width
        if start * end < 0:
            crossing = -start / slope
            peak = max(peak, abs(phase +
                       (start * crossing + .5 * slope * crossing**2) * 1e-6))
        phase += .5 * (start + end) * width * 1e-6
        peak = max(peak, abs(phase))
    bound = initial_error_ui + uncertainty_ui + peak
    return dict(bound_ui=bound, margin_ui=available_ui-bound,
                admissible=bound < available_ui, peak_drift_ui=peak,
                final_drift_ui=phase, duration_ui=duration)
