"""Small-signal self-bias/coupling diagnostic; not periodically switching operation."""
from lo_sine_speed import main

if __name__ == '__main__':
    main(analysis='ac', entrypoint=__file__)
