# SPDX-License-Identifier: Apache-2.0
# Materialize the pinned GF180 reference inverter into disposable scratch.
crashbackups stop
path search +$::env(PDKPATH)/libs.ref/gf180mcu_fd_sc_mcu7t5v0/mag
load gf180mcu_fd_sc_mcu7t5v0__inv_1
select top cell
flatten inverter
load inverter
save
quit -noprompt
