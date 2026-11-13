import re,glob,statistics
for lib in sorted(glob.glob('/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu*5v0/lib/*.lib')):
    if not re.search(r'(tt_025C_3v30|ff_125C_3v60)', lib): continue
    t=open(lib).read()
    cells=re.split(r'\n\s*cell\s*\(', t)[1:]
    per=[]; byname={}
    for c in cells:
        name=c.split(')')[0].strip('" ')
        v=[float(x) for x in re.findall(r'leakage_power\s*\(\s*\)\s*\{\s*value\s*:\s*([-0-9.eE+]+)', c)]
        if v: per.append(max(v)); byname[name.split('__')[-1]]=max(v)
    print(lib.split('/')[-1], 'uW; cells',len(per),'mean(max-state)',statistics.mean(per),'median',statistics.median(per),'max',max(per),
          {k:byname.get(k) for k in ('nand2_1','inv_1','dffrnq_1','buf_8','fillcap_4','filltie')})
