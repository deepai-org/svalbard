# Extend LibreLane's standard-cell grid to every foundry SRAM leaf. All SRAMs
# use the north orientation selected by run_gf180.py.
source $::env(SCRIPTS_DIR)/openroad/common/pdn_cfg.tcl

set lnp64_sram_instances {}
foreach inst [[ord::get_db_block] getInsts] {
    if {[[$inst getMaster] getName] eq "gf180mcu_fd_ip_sram__sram512x8m8wm1"} {
        lappend lnp64_sram_instances [$inst getName]
    }
}

if {[llength $lnp64_sram_instances] > 0} {
    define_pdn_grid -macro -cells gf180mcu_fd_ip_sram__sram512x8m8wm1 \
        -name lnp64_sram_grid -starts_with POWER \
        -halo "$::env(PDN_HORIZONTAL_HALO) $::env(PDN_VERTICAL_HALO)"
    add_pdn_connect -grid lnp64_sram_grid \
        -layers "$::env(PDN_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"
    add_pdn_connect -grid lnp64_sram_grid \
        -layers "$::env(PDN_VERTICAL_LAYER) Metal3"
    add_pdn_stripe -grid lnp64_sram_grid -layer Metal4 \
        -width 2.36 -offset 1.18 -spacing 0.28 -pitch 426.86 \
        -starts_with GROUND -number_of_straps 2
    add_pdn_stripe -grid lnp64_sram_grid -layer Metal4 \
        -width 4.00 -offset 65.93 -spacing 0.28 -pitch 50 \
        -starts_with GROUND -number_of_straps 7
}
