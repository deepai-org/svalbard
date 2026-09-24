"""Complementary real LO chains driving actual mixer; controlled RF termination."""
from lo_sine_speed import main

if __name__ == '__main__':
    main(analysis='mixer', entrypoint=__file__)
