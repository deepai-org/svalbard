# SPDX-License-Identifier: Apache-2.0
# Materialize the pinned default 7-track standard-library NAND2.
crashbackups stop
path search +$::env(PDKPATH)/libs.ref/gf180mcu_fd_sc_mcu7t5v0/mag
load gf180mcu_fd_sc_mcu7t5v0__nand2_1
select top cell
flatten nand2_std_5v
load nand2_std_5v
property FIXED_BBOX 0 0 2.80 3.92
save nand2_std_5v
gds write /work/nand2_std_5v.gds
quit -noprompt
