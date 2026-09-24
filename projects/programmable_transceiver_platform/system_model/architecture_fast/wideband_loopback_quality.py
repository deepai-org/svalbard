"""Wideband fixture for the shared nonlinear loopback quality runner."""
from functools import partial
from rf_modulated_quality import Multicarrier
from loopback_quality import simulate as simulate_loopback, main as run_quality

simulate=partial(simulate_loopback,waveform=Multicarrier(seed=804))

def main():
    return run_quality(wideband=True)

if __name__=='__main__':main()
