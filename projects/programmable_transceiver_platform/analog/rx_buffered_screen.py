#!/usr/bin/env python3
"""Compare ideal and transistor-buffered LO drive in the split I/Q receiver."""
from rx_split_screen import main

if __name__ == '__main__':
    main(buffered=True, entrypoint=__file__)
