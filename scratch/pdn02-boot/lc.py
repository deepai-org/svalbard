# Adds ripple-droop supply corners to libchar.py (ss, 32 C) and runs it; PDN-02 boot-path study.
import sys
sys.path.insert(0,'/home/ubuntu/svalbard/projects/programmable_transceiver_platform/verification/digital_hardening')
import libchar as L
for v in (2.84, 3.00, 3.19, 3.35):
    L.CORNERS['ss_032C_%dv%02d'%(int(v),round((v-int(v))*100))]=('ss',32,v)
sys.argv=['libchar.py']+sys.argv[1:]
L.main()
