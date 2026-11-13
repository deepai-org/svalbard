import re, glob, statistics
out = {}
for tag in ('tt_025C_3v30', 'ff_125C_3v60', 'ff_n40C_3v60'):
    t = open(f'/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__{tag}.lib').read()
    unit = re.search(r'leakage_power_unit\s*:\s*"?([^";]+)', t).group(1)
    d = {}
    for c in re.split(r'\n\s*cell\s*\(', t)[1:]:
        name = c.split(')')[0].strip('" ').split('__')[-1]
        v = [float(x) for x in re.findall(r'leakage_power\s*\(\s*\)\s*\{[^}]*?value\s*:\s*"?([-0-9.eE+]+)', c)]
        if v: d[name] = sum(v)/len(v)
    out[tag] = d
    print(tag, unit, len(d), {k: d.get(k) for k in ('inv_1', 'nand2_1', 'dffrnq_1', 'buf_8', 'clkbuf_16')})
a, b = out['tt_025C_3v30'], out['ff_125C_3v60']
r = [b[k]/a[k] for k in a if k in b and a[k] > 0]
print('ratio ff_125C_3v60 / tt_025C_3v30: median %.1f mean %.1f min %.1f max %.1f' % (statistics.median(r), statistics.mean(r), min(r), max(r)))
