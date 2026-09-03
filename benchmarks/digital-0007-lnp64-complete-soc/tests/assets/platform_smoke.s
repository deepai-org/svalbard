.text
  LI r1, 0x40001000
  LI r2, 0x55667788
  ST.W [r1, 0], r2
  LWU r3, [r1, 0]
  BNE r3, r2, bad

  LI r1, 0x10000008
  LI r2, 1
  ST.W [r1, 0], r2
  LI r1, 0x10000000
  LI r2, 0x5a
  ST.W [r1, 0], r2
  EXIT r0

bad:
  LI r1, 1
  EXIT r1
