for c in wtx8_aux wtx_ser8d wtx_mux8 pt_wiredtx8; do
  until [ $(pgrep -c -f '^\S*ngspice -b tb.sp') -lt 3 ]; do sleep 60; done
  date; /usr/bin/time -f "%e s" python3 ext.py $c
done
