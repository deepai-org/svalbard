"""Dense-reference variant of the shared acquisition/calibration screen."""
from managed_dense_reference import ManagedDenseReferenceChip
from managed_limited_calibration_screen import run_calibration

def main():
    return run_calibration(ManagedDenseReferenceChip,'connected-managed-dense-calibration.json')

if __name__=='__main__':main()
