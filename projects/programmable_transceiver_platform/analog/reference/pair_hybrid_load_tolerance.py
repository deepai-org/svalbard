from pair_hybrid_load_dc import main

if __name__ == '__main__':
    main('.options reltol=1e-5 vntol=1e-8 abstol=1e-14\nILOAD OH 0 DC 0\n', entrypoint=__file__)
