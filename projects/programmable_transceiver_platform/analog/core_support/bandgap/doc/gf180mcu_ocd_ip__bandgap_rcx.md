
# CACE Summary for gf180mcu_ocd_ip__bandgap

**netlist source**: rcx

|      Parameter       |         Tool         |     Result      | Min Limit  |  Min Value   | Typ Target |  Typ Value   | Max Limit  |  Max Value   |  Status  |
| :------------------- | :------------------- | :-------------- | ---------: | -----------: | ---------: | -----------: | ---------: | -----------: | :------: |
| Tempco -40 to 125 C  | ngspice              | tempco_m40_125_ppmC  |               ​ |          ​ |            ​ |          ​ |    50 ppm/°C |          ​ |   Skip 🟧    |
| Tempco 0 to 85 C     | ngspice              | tempco_m0_85_ppmC    |               ​ |          ​ |            ​ |          ​ |    25 ppm/°C |          ​ |   Skip 🟧    |
| Vbg at 27 C          | ngspice              | vbg_27               |          1.15 V |          ​ |            ​ |          ​ |        1.3 V |          ​ |   Skip 🟧    |
| V(125C) - V(-40C)    | ngspice              | vslope_mV            |               ​ |          ​ |            ​ |          ​ |         0 mV |          ​ |   Skip 🟧    |
| V(125C) - V(-40C)    | ngspice              | vslope_mV            |            0 mV |          ​ |            ​ |          ​ |            ​ |          ​ |   Skip 🟧    |
| Vbg at 27 C          | ngspice              | vbg_27               |          1.15 V |          ​ |            ​ |          ​ |        1.3 V |          ​ |   Skip 🟧    |
| Tempco -40 to 125 C  | ngspice              | tempco_m40_125_ppmC  |               ​ |          ​ |            ​ |          ​ |    50 ppm/°C |          ​ |   Skip 🟧    |
| Vbg at 27 C          | ngspice              | vbg_27               |          1.15 V |          ​ |            ​ |          ​ |        1.3 V |          ​ |   Skip 🟧    |
| Vbg at 27 C          | ngspice              | vbg_27               |          1.15 V |          ​ |            ​ |          ​ |        1.3 V |          ​ |   Skip 🟧    |


## Plots

## vbg_vs_trim

![vbg_vs_trim](./gf180mcu_ocd_ip__bandgap/rcx/vbg_vs_trim.png)

## vslope_vs_trim

![vslope_vs_trim](./gf180mcu_ocd_ip__bandgap/rcx/vslope_vs_trim.png)
