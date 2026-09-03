# SPDX-FileCopyrightText: 2026 Deep AI, Inc.
# SPDX-License-Identifier: Apache-2.0
# PCIe endpoint, bidirectional DMA, MSI, and IOMMU-revocation smoke.

.text
  # Discover the reset-granted PCIe Device.
  LI r10, 2
  LSLI r10, r10, 39
  ORI r10, r10, 1
  LI r3, 3
  device.get r11, r10, r3
  BLE r11, r0, bad

  # Establish IOVA page zero over SDRAM backing offset 0x1000.
  LI r13, 3
  LSLI r13, r13, 39
  ORI r13, r13, 1
  window.new r12, r0
  window.scope r12, r12, r13
  window.device r12, r12, r11
  window.pin r12, r12
  window.seal r14, r12
  BLE r14, r0, bad
  LI r2, 0
  LI r3, 0x1000
  LI r4, 0x1000
  window.remap_one r15, r14, r2, r3, r4
  BLE r15, r0, bad

  # Enable the endpoint and wait for enumeration, bus mastering, and MSI.
  LI r20, 0x10002004
  LI r2, 1
  ST.W [r20, 0], r2
  LI r20, 0x10002000
  LI r21, 0x7
link_wait:
  LWU r2, [r20, 0]
  AND r2, r2, r21
  BNE r2, r21, link_wait

  # Seed four words in the authorized page.
  LI r22, 0x40001000
  LI r2, 0x11223344
  ST.W [r22, 0], r2
  LI r2, 0x55667788
  ST.W [r22, 4], r2
  LI r2, 0x99aabbcc
  ST.W [r22, 8], r2
  LI r2, 0xddeeff00
  ST.W [r22, 12], r2

  # SoC-to-host DMA to host address 0x1000.
  LI r23, 0x10002010
  ST.W [r23, 0], r0
  ST.W [r23, 4], r0
  LI r2, 0x1000
  ST.W [r23, 8], r2
  ST.W [r23, 12], r0
  LI r2, 16
  ST.W [r23, 16], r2
  LI r2, 1
  ST.W [r23, 20], r2
dma_write_wait:
  LWU r2, [r23, 24]
  ANDI r3, r2, 3
  BEQ r3, r0, dma_write_wait
  ANDI r3, r2, 1
  BEQ r3, r0, bad
  ST.W [r23, 24], r3

  # Clear the page, then read the same data back from host memory.
  ST.W [r22, 0], r0
  ST.W [r22, 4], r0
  ST.W [r22, 8], r0
  ST.W [r22, 12], r0
  LI r2, 3
  ST.W [r23, 20], r2
dma_read_wait:
  LWU r2, [r23, 24]
  ANDI r3, r2, 3
  BEQ r3, r0, dma_read_wait
  ANDI r3, r2, 1
  BEQ r3, r0, bad
  ST.W [r23, 24], r3
  LWU r2, [r22, 0]
  LI r3, 0x11223344
  BNE r2, r3, bad
  LWU r2, [r22, 4]
  LI r3, 0x55667788
  BNE r2, r3, bad
  LWU r2, [r22, 8]
  LI r3, 0x99aabbcc
  BNE r2, r3, bad
  LWU r2, [r22, 12]
  LI r3, 0xddeeff00
  BNE r2, r3, bad

  # Generate MSI vector zero after the root enables it.
  LI r20, 0x1000200c
  LI r2, 1
  ST.W [r20, 0], r2

  # Unmap IOVA zero, wait for acknowledgment, and prove DMA is denied.
  LI r2, 0
  LI r3, -1
  LI r4, 0x1000
  window.remap_one r15, r14, r2, r3, r4
  BLE r15, r0, bad
ack_wait:
  window.acknowledged r16, r14
  BLT r16, r15, ack_wait
  LI r2, 0x2000
  ST.W [r23, 8], r2
  LI r2, 1
  ST.W [r23, 20], r2
dma_deny_wait:
  LWU r2, [r23, 24]
  ANDI r3, r2, 3
  BEQ r3, r0, dma_deny_wait
  ANDI r3, r2, 2
  BEQ r3, r0, bad
  LWU r3, [r23, 28]
  BNE r3, r0, bad

  lifecycle.destroy r1, r14
  EXIT r0

bad:
  LI r1, 1
  EXIT r1
