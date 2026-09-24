"""Include measured CDAC current in reference-node charge balance."""
from analyze_reference_partial_balance import main

if __name__ == '__main__':
    main(loaded=True, entrypoint=__file__)
