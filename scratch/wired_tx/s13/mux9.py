"""shim: the revision-3 mux schematic lives in analog/wired_tx/wtx_mux8.py"""
import sys
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx')
from wtx_mux8 import *  # noqa
from wtx_mux8 import netlist, PORTS, P, NTR  # noqa
