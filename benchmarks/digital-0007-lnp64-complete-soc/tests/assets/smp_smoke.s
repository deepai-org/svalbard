# SPDX-FileCopyrightText: 2026 Deep AI, Inc.
# SPDX-License-Identifier: Apache-2.0
# Sixteen persistent threads rendezvous, update one coherent word, and exit.

.data
counter: .quad 0
start:   .quad 0
tids:    .zero 120
         .zero 8
stacks:  .zero 3840

.text
  LI r7, 15
  LI r4, stacks
  LI r5, 256
  LI r8, tids

create:
  LI r2, child
  LI r3, 0
  thread.new r9, r2, r3, r4, r5
  BLE r9, r0, bad
  ST [r8, 0], r9
  ADDI r8, r8, 8
  ADD r4, r4, r5
  ADDI r7, r7, -1
  BNE r7, r0, create

  LI r1, start
  LI r2, 1
  SD.RL.D 0(r1), r2
  LI r4, 15
  FUTEX_WAKE r6, r1, r4

  LI r1, counter
  LI r3, 15
wait_done:
  LD.AQ.D r2, 0(r1)
  BNE r2, r3, wait_done
  EXIT r0

child:
  LI r1, start
  LI r5, -1
wait_start:
  LD.AQ.D r3, 0(r1)
  BNE r3, r0, count
  FUTEX_WAIT r6, r1, r0, r5
  BNE r6, r0, bad_child
  BEQ r0, r0, wait_start

count:
  LI r1, counter
  LI r2, 1
  AMO.ADD.D r3, (r1), r2
  thread.exit

bad_child:
  LI r1, counter
  LI r2, 0x10000
  AMO.ADD.D r3, (r1), r2
  thread.exit

bad:
  LI r1, 1
  EXIT r1
