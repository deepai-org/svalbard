"""Actual acquisition/calibration with unified driver, PLL and loaded reference."""
from managed_feedback_calibration_screen import main as run_calibration_screen
from managed_unified_reference import ManagedUnifiedReferenceChip

def main():
    run_calibration_screen(
        ManagedUnifiedReferenceChip,
        report_name='connected-managed-unified-calibration.json',
        coupling_limitation='Driver rail pulls RF PLL; reference load is real but reference voltage and buffer current share the coupled driver rail.',
    )

if __name__ == '__main__':
    main()
