#!/usr/bin/env python3
"""Summarize aborted Gear2 evidence without asserting settling or lock."""
from analyze_pll_aborted_settling import main

if __name__ == "__main__":
    main(gear=True)
