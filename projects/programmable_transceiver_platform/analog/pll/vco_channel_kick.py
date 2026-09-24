"""Channel charge perturbation of the ring; deterministic diagnostic only."""
from vco_charge_kick import main

if __name__ == '__main__':
    main('channel', entrypoint=__file__)
