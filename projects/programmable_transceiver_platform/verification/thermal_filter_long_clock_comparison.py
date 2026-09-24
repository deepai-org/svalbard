"""Compatibility entry point; implementation is thermal_filter_clock_comparison."""
import thermal_filter_batched
from thermal_filter_local_guard import safe_region
# Preserve the historical import side effect used by the stressed-quality runner.
thermal_filter_batched.safe_region=safe_region
from thermal_filter_clock_comparison import BatchedFilter, main as run_comparison


def main():
    return run_comparison('long')


if __name__=='__main__':
    main()
