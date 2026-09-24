"""Matched reltol-only replay using the shared convergence runner."""
from cdac_probe_convergence import main

if __name__ == '__main__':
    main('option reltol=1e-5\n', entrypoint=__file__)
