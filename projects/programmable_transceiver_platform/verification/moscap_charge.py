"""Charge-equivalent GF180 MOSCAP overlay for long absolute-time transients.

The native nonlinear-C expansion uses a 1 fs artificial RC differentiator.
Integrating the PDK's C(V) analytically avoids that numerical time constant.
This changes the simulator realization, not the two-terminal C(V) model.
"""
import re
from pathlib import Path


def overlay(pdk, corner='typical'):
    source = (Path(pdk)/'ngspice/sm141064.spice').read_text()
    sections = (Path(pdk)/'ngspice/sm141064.ngspice').read_text()
    params = re.search(rf'^\.lib moscap_{corner}\s*$(.*?)^\.endl moscap_{corner}\s*$',
                       sections, re.M | re.S).group(1)
    params = '\n'.join(line for line in params.splitlines() if line.startswith('.param'))
    block = re.search(r'^\.lib moscap\s*$(.*?)^\.endl moscap\s*$', source, re.M | re.S).group(1)
    cells = re.findall(r'(^\.subckt (\w+).*?^\.ends[^\n]*)', block, re.M | re.S)
    assert len(cells) == 8, 'unexpected PDK MOSCAP family'
    result = ['* Exact integral of the retained PDK MOSCAP C(V); scaled charge state.', params]
    for cell, name in cells:
        # Strictly recognize the source equation; a changed PDK must be reviewed.
        expected = (f"c_moscap 1 2 c='{name}_corner*c_length*c_width*"
                    "(cvar1+cvar2*tanh(cvar3*v(1,2)+cvar4))' dtemp=dtemp")
        assert expected in cell, f'changed PDK capacitance expression: {name}'
        header = cell.splitlines()[0]+' m=1'
        constants = [line for line in cell.splitlines() if line.startswith('.param')]
        def logcosh(z):
            return f'(abs({z})+ln(1+exp(-2*abs({z})))-ln(2))'
        z = '(cvar3*v(1,2)+cvar4)'
        charge = (f'{name}_corner*c_length*c_width*'
                  f'(cvar1*v(1,2)+cvar2/cvar3*({logcosh(z)}-{logcosh("cvar4")}))')
        result += [header, *constants,
                   # IL=1e12*Q; Vstate=1e3*dQ/dt; Iport=m*dQ/dt.
                   # L=1n keeps the bench's 10 aF global shunt from creating
                   # a slow artificial resonance in this numerical state.
                   f'Bcharge 0 QSTATE I=1e12*({charge})',
                   'Lcharge QSTATE 0 1n',
                   'Gcharge 1 2 QSTATE 0 {m/1e3}', f'.ends {name}']
    return '\n'.join(result)+'\n'
