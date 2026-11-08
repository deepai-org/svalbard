# gf180mcu_ocd_ip__bandgap

- Description: Trimmable bandgap voltage reference for the Chipalooza harness
- PDK: gf180mcuD

## Authorship

- Designer: R. Timothy Edwards
- Company: Open Circuit Design, LLC
- Created: September 22, 2026
- License: Apache 2.0
- Last modified: None

## Pins

- vdd
  + Description: 3.3 V analog supply.  The bandgap core and its output buffer are built from 3.3 V devices.  Only the voltage bias generator downstream of it may run from a 5 V rail.

  + Direction: inout
  + Type: power
  + Vmin: 3.0
  + Vmax: 3.6
- vss
  + Description: Analog ground
  + Direction: inout
  + Type: ground
- dvdd
  + Description: 3.3 V digital supply;  the trim bits and ena are in this domain
  + Direction: inout
  + Type: power
  + Vmin: 3.0
  + Vmax: 3.6
- dvss
  + Description: Digital ground
  + Direction: inout
  + Type: ground
- ena
  + Description: Circuit enable
  + Direction: input
  + Type: digital
- trim[15:0]
  + Description: Trim, as a THERMOMETER code.  Only the number of bits set is meaningful, so there are 17 distinct settings, 0 through 16.
  + Direction: input
  + Type: digital
- ibias1_250n
  + Description: 250 nA bias current input
  + Direction: input
  + Type: signal
- ibias2_1u
  + Description: 1 uA bias current input
  + Direction: input
  + Type: signal
- vbg
  + Description: Buffered bandgap reference output
  + Direction: output
  + Type: signal

## Default Conditions

- corner
  + Display: Corner
  + Description: MOS process corner
  + Typical: typical
- corner_pnp
  + Display: PNP corner
  + Description: Vertical PNP corner.  SWEPT INDEPENDENTLY of the MOS corner, not correlated with it:  the bipolar is formed by different implants than the MOS Vt adjust, and the PDK ships it as its own library for that reason.  Correlating them would silently exclude real dice, e.g. (MOS ff, PNP wcs).
Note the direction is the opposite of what "best case speed" suggests.  bcs raises the saturation current (is x1.13), and V_BE = V_T*ln(I_C/I_S), so a HIGHER I_S gives a LOWER V_BE and pushes the reference DOWN:
    bcs   -V_T*ln(1.13)    = -3.16 mV at 27 C
    wcs   +V_T*ln(1/0.87)  = +3.60 mV
About 6.8 mV of spread, against a 7.2 mV trim step at nominal --- roughly one trim code.  It shifts the CTAT term only:  I_S cancels in the PTAT term, since both PNPs take the same corner multiplier.

  + Typical: typical
- corner_cap
  + Display: Capacitor corner
  + Description: MOM capacitor corner.  Left at typical:  the caps are compensation and decoupling, and every parameter here is a DC measurement, in which capacitors are open circuits.  It matters for stability and startup -- which is exactly what the v2 capacitor correction was for, and why those need their own parameters.

  + Typical: typical
- corner_dio
  + Display: Diode corner
  + Description: Left at typical deliberately.  The only non-PNP diodes in this block are antenna tie-downs on the digital trim inputs, which have no bearing on the reference.

  + Typical: typical
- corner_res
  + Display: Resistor corner
  + Description: Resistor model corner
  + Typical: typical
- temperature
  + Display: Temperature
  + Description: Ambient temperature.  DELIBERATELY NOT declared with minimum, maximum and step:  the sweep is done inside the testbench by the ngspice "dc temp -40 125 1" statement, and declaring it here as a stepped condition makes CACE enumerate it into one netlist per temperature point as well -- 168 runs for what should be one. The range lives in the template;  this entry only pins the nominal so every parameter gets a single run per corner.

  + Unit: °C
  + Typical: 27
- trim
  + Display: Trim
  + Description: Number of thermometer bits set, 0 to 16
  + Typical: 8

## Symbol

![Symbol of gf180mcu_ocd_ip__bandgap](gf180mcu_ocd_ip__bandgap_symbol.svg)

## Schematic

![Schematic of gf180mcu_ocd_ip__bandgap](gf180mcu_ocd_ip__bandgap_schematic.svg)

## Layout

![Layout of gf180mcu_ocd_ip__bandgap with white background](gf180mcu_ocd_ip__bandgap_w.png)
![Layout of gf180mcu_ocd_ip__bandgap with black background](gf180mcu_ocd_ip__bandgap_b.png)
