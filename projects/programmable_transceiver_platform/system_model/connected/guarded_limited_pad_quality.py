"""Guarded/current-limited variant of unified pad quality."""
from unified_pad_quality import main as run_quality

def main(mode=0):
    return run_quality(mode,guarded=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--mode',type=int,choices=(0,1),default=0)
    main(parser.parse_args().mode)
