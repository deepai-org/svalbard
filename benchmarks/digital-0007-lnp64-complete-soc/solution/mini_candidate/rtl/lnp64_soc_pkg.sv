package lnp64_soc_pkg;
  localparam int unsigned CORE_COUNT = 4;
  localparam int unsigned CONTEXTS_PER_CORE = 4;
  localparam int unsigned VLEN = 512;
  localparam int unsigned CORE_CLOCK_HZ = 200_000_000;
  localparam int unsigned SDRAM_CLOCK_HZ = 100_000_000;
  localparam int unsigned SRAM_CLOCK_MAX_HZ = 50_000_000;
  localparam int unsigned PIPE_CLOCK_HZ = 125_000_000;

  localparam logic [1:0] BOOT_SDHC = 2'b00;
  localparam logic [1:0] BOOT_UART = 2'b01;
  localparam logic [1:0] BOOT_JTAG = 2'b10;
endpackage
