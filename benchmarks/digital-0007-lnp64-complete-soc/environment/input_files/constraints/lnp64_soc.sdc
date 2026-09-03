create_clock -name core_clk -period 5.000 [get_ports clk_200_i]
create_clock -name pipe_clk -period 8.000 [get_ports pipe_clk_125_i]
create_clock -name jtag_clk -period 40.000 [get_ports jtag_tck_i]
create_generated_clock -name sdram_clk -source [get_ports clk_200_i] -divide_by 2 [get_ports sdram_clk_o]
create_generated_clock -name sd_clk -source [get_ports clk_200_i] -divide_by 8 [get_ports sd_clk_o]

set_clock_uncertainty 0.100 [get_clocks core_clk]
set_clock_uncertainty 0.150 [get_clocks {pipe_clk sdram_clk sd_clk}]

set_input_delay 0.500 -clock core_clk [get_ports {boot_sel_i[*] entropy_bit_i entropy_valid_i}]
set_output_delay 0.500 -clock core_clk [get_ports {uart_tx_o entropy_ready_o boot_done_o boot_error_o core_alive_o[*]}]
set_input_delay 2.000 -clock sd_clk [get_ports {sd_cmd_i sd_dat_i[*]}]
set_output_delay 2.000 -clock sd_clk [get_ports {sd_cmd_o sd_cmd_oe_o sd_dat_o[*] sd_dat_oe_o}]
set_input_delay 0.500 -clock pipe_clk [get_ports {pipe_rxdata_i[*] pipe_rxdatak_i[*] pipe_rxvalid_i pipe_phystatus_i pipe_rxelecidle_i pipe_rxstatus_i[*]}]
set_output_delay 0.500 -clock pipe_clk [get_ports {pipe_txdata_o[*] pipe_txdatak_o[*] pipe_txelecidle_o pipe_powerdown_o[*] pipe_rate_o pipe_reset_no pipe_rxpolarity_o pipe_txcompliance_o pipe_txdetectrx_loopback_o}]
set_input_delay 0.750 -clock sdram_clk [get_ports sdram_dq_i[*]]
set_output_delay 0.750 -clock sdram_clk [get_ports {sdram_cke_o sdram_cs_no sdram_ras_no sdram_cas_no sdram_we_no sdram_ba_o[*] sdram_addr_o[*] sdram_dqm_o[*] sdram_dq_o[*] sdram_dq_oe_o[*]}]
set_input_delay 2.000 -clock jtag_clk [get_ports {jtag_tms_i jtag_tdi_i}]
set_output_delay 2.000 -clock jtag_clk [get_ports jtag_tdo_o]

set_false_path -from [get_ports {rst_ni pcie_perst_ni jtag_trst_ni uart_rx_i}]
set_clock_groups -asynchronous \
  -group [get_clocks {core_clk sdram_clk sd_clk}] \
  -group [get_clocks pipe_clk] \
  -group [get_clocks jtag_clk]
