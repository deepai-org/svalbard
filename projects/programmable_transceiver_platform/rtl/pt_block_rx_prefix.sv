// Routing-specific receiver; control logic is shared.
`define PT_RX_MODULE pt_block_rx_prefix
`define PT_RX_ROUTE pt_block_route_prefix
`include "pt_block_rx_routed.vh"
`undef PT_RX_ROUTE
`undef PT_RX_MODULE
