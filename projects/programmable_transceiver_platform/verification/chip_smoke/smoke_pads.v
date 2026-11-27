// Behavioural provider pad cells for the chip smoke bench (verification/chip_smoke). Same function as the provider
// Verilog (gf180mcu_fd_io.v: Y = PAD & IE, PAD = OE ? A : pull), but STRICT where the provider model is lenient:
//  * any control pin (IE, OE, A while OE, PU, PD, CS, SL, PDRV*) at X / Z, or a cell rail pin not at its level
//    (DVDD / VDD = 1, DVSS / VSS = 0), makes Y and PAD X, so an untied or misbound pad pin cannot pass;
//  * the pulls are modelled (weak, only with OE = 0 and exactly one of PU / PD), also on in_c (the provider in_c model
//    ignores PU / PD), so a strap or reset pad without its pull floats in the bench as it would on the board.
`timescale 1ns/1ps
module smoke_pad_core(input wire CS, SL, IE, OE, PU, PD, A, PDRV0, PDRV1, DVDD, DVSS, VDD, VSS, inout wire PAD, output wire Y);
 wire bad = (^{CS, SL, IE, OE, PU, PD, PDRV0, PDRV1} === 1'bx) || DVDD !== 1'b1 || VDD !== 1'b1 || DVSS !== 1'b0 || VSS !== 1'b0;
 assign PAD = bad ? 1'bx : (OE ? A : 1'bz);
 assign (weak1, weak0) PAD = (!bad && OE === 1'b0 && PU === 1'b1 && PD === 1'b0) ? 1'b1 :
                             (!bad && OE === 1'b0 && PU === 1'b0 && PD === 1'b1) ? 1'b0 : 1'bz;
 assign Y = bad ? 1'bx : (IE & PAD);
endmodule
module gf180mcu_fd_io__bi_24t(input wire CS, SL, IE, OE, PU, PD, A, inout wire PAD, output wire Y, inout wire DVDD, DVSS, VDD, VSS);
 smoke_pad_core c(.CS(CS), .SL(SL), .IE(IE), .OE(OE), .PU(PU), .PD(PD), .A(A), .PDRV0(1'b0), .PDRV1(1'b0),
  .DVDD(DVDD), .DVSS(DVSS), .VDD(VDD), .VSS(VSS), .PAD(PAD), .Y(Y));
endmodule
// layout cell of the host outputs (bi_t with PDRV pins)
module selected_host_output(input wire A, CS, IE, OE, PD, PDRV0, PDRV1, PU, SL, inout wire PAD, output wire Y, inout wire DVDD, DVSS, VDD, VSS);
 smoke_pad_core c(.CS(CS), .SL(SL), .IE(IE), .OE(OE), .PU(PU), .PD(PD), .A(A), .PDRV0(PDRV0), .PDRV1(PDRV1),
  .DVDD(DVDD), .DVSS(DVSS), .VDD(VDD), .VSS(VSS), .PAD(PAD), .Y(Y));
endmodule
// input-only cell: IE is always on in the cell
module gf180mcu_fd_io__in_c(input wire PU, PD, inout wire PAD, output wire Y, inout wire DVDD, DVSS, VDD, VSS);
 smoke_pad_core c(.CS(1'b1), .SL(1'b0), .IE(1'b1), .OE(1'b0), .PU(PU), .PD(PD), .A(1'b0), .PDRV0(1'b0), .PDRV1(1'b0),
  .DVDD(DVDD), .DVSS(DVSS), .VDD(VDD), .VSS(VSS), .PAD(PAD), .Y(Y));
endmodule
module gf180mcu_fd_io__asig_5p0(inout wire ASIG5V, DVDD, DVSS, VDD, VSS); endmodule
module gf180mcu_fd_io__dvdd(inout wire DVDD, DVSS, VSS); endmodule
module gf180mcu_fd_io__dvss(inout wire DVDD, DVSS, VDD); endmodule
