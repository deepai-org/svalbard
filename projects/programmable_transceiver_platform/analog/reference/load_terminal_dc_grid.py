"""Independent drain/gate DC grid over the measured reference-load envelope."""
from load_terminal_dc import main

if __name__ == "__main__":
    main(grid=True, entrypoint=__file__)
