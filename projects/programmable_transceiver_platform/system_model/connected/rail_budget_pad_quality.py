"""Unified driver/PLL/reference candidate on independent traffic quality."""
from shared_pad_quality import main as run_pad_quality, cli

def main(mode=0):
    run_pad_quality(mode, rail_budget=True)

if __name__ == '__main__':
    cli(rail_budget=True)
