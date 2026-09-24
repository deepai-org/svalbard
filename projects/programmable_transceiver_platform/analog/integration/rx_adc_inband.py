"""Replay in-band RF stimulus through actual receiver and ADC."""
from rx_adc_event_offsets import main

if __name__ == "__main__":
 main("/work/separated/connected.dat", entrypoint=__file__)
