"""EM screen (round 3): worst-corner currents x per-um / per-cut fractions of the netres two-terminal solves (scratch/rf_rx/netres/netres.log).
Two-terminal solves do not superpose currents on shared trunks: the result is an estimate, not sign-off."""
import re
I = dict(VDD=18.6, VSS=18.6, vtk=18.6, tail=18.6, tailx=18.6, src_p=9.3, src_n=9.3, x_p=9.3, x_n=9.3, tank_p=9.3, tank_n=9.3)
for l in open('/home/ubuntu/svalbard/scratch/rf_rx/netres/netres.log'):
    t = l.split()
    if len(t) > 3 and t[1] == 'typ' and t[0] in I and t[2].startswith('port|') or (len(t) > 3 and t[1] == 'typ' and t[2] in ('XMN17.d|XMN118.s', 'XMN249.d|XMN431.s', 'XMN468.d|XMN650.s')):
        m = re.search(r'max/cut ([\d.]+)', l); w = re.search(r'narrowest ([\d.]+) um', l)
        if m and w: print(t[0], t[2], 'mA/cut %.2f' % (I[t[0]] * float(m.group(1))), 'mA/um on narrowest %.2f' % (I[t[0]] / float(w.group(1))))
