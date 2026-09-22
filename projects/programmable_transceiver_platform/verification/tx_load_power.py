"""Currents delivered by ideal bias sources into verified TX load resistors."""
def delivered_currents(op,on,rfp,rfn):
    return (4.30-op-on)/100, (3.78-rfp-rfn)/50
