"""Static switching-region diagnostic of actual three-inverter LO chain."""
from lo_sine_speed import main

if __name__ == '__main__':
    main(analysis='dc', entrypoint=__file__)
