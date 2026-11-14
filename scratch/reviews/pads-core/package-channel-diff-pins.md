| Signal | Old: site / bond / contact | New: site / bond / contact | Old F+B mm (delay ps) | New F+B mm (delay ps) | bond mm old -> new | cls old -> new | Change |
|---|---|---|---|---|---|---|---|
| D2H_D[0] | clk_pad / 1 / 8 | clk_pad / 1 / 8 | 1.99+4.13=6.12 (36.2) | 1.99+4.13=6.12 (36.2) | 2.79 -> 2.79 | host -> host | none |
| RESET_N | rst_n_pad / 2 / 7 | rst_n_pad / 2 / 7 | 2.82+4.01=6.83 (40.4) | 2.82+4.01=6.83 (40.4) | 2.67 -> 2.67 | spi -> spi | none |
| D2H_D[1] | bidir[0] / 3 / 6 | bidir[0] / 3 / 6 | 3.11+3.62=6.73 (39.8) | 3.11+3.62=6.73 (39.8) | 2.55 -> 2.55 | host -> host | none |
| D2H_D[2] | bidir[1] / 4 / 5 | bidir[1] / 4 / 5 | 3.17+3.01=6.18 (36.5) | 3.17+3.01=6.18 (36.5) | 2.45 -> 2.45 | host -> host | none |
| D2H_D[3] | bidir[2] / 5 / 4 | bidir[2] / 5 / 4 | 3.18+2.56=5.74 (33.9) | 3.18+2.56=5.74 (33.9) | 2.36 -> 2.36 | host -> host | none |
| D2H_D[4] | bidir[3] / 6 / 3 | bidir[3] / 6 / 3 | 3.13+1.88=5.01 (29.6) | 3.13+1.88=5.01 (29.6) | 2.29 -> 2.29 | host -> host | none |
| D2H_D[5] | bidir[4] / 7 / 2 | bidir[4] / 7 / 2 | 3.09+1.13=4.22 (24.9) | 3.09+1.13=4.22 (24.9) | 2.24 -> 2.24 | host -> host | none |
| D2H_CLK | bidir[5] / 8 / 1 | bidir[5] / 8 / 1 | 2.18+0.76=2.94 (17.4) | 2.18+0.76=2.94 (17.4) | 2.21 -> 2.21 | host -> host | none |
| D2H_D[6] | bidir[6] / 10 / 70 | bidir[6] / 10 / 70 | 2.18+0.75=2.93 (17.3) | 2.18+0.75=2.93 (17.3) | 2.21 -> 2.21 | host -> host | none |
| D2H_D[7] | bidir[7] / 11 / 69 | bidir[7] / 11 / 69 | 3.16+1.23=4.39 (25.9) | 3.16+1.23=4.39 (25.9) | 2.24 -> 2.24 | host -> host | none |
| D2H_D[8] | bidir[8] / 12 / 68 | bidir[8] / 12 / 68 | 3.45+1.82=5.27 (31.1) | 3.45+1.82=5.27 (31.1) | 2.29 -> 2.29 | host -> host | none |
| D2H_D[9] | bidir[9] / 13 / 67 | bidir[9] / 13 / 67 | 3.41+2.53=5.94 (35.1) | 3.41+2.53=5.94 (35.1) | 2.36 -> 2.36 | host -> host | none |
| HOST_CS_N | bidir[10] / 14 / 66 | bidir[10] / 14 / 66 | 3.38+3.21=6.59 (38.9) | 3.38+3.21=6.59 (38.9) | 2.45 -> 2.45 | spi -> spi | none |
| HOST_SCLK | bidir[11] / 15 / 65 | bidir[11] / 15 / 65 | 3.19+3.78=6.97 (41.2) | 3.19+3.78=6.97 (41.2) | 2.55 -> 2.55 | spi -> spi | none |
| HOST_MOSI | bidir[12] / 16 / 64 | bidir[12] / 16 / 64 | 2.59+3.78=6.37 (37.6) | 2.59+3.78=6.37 (37.6) | 2.67 -> 2.67 | spi -> spi | none |
| HOST_MISO | bidir[13] / 17 / 63 | bidir[13] / 17 / 63 | 2.07+3.94=6.01 (35.5) | 2.07+3.94=6.01 (35.5) | 2.79 -> 2.79 | spi -> spi | none |
| WIRE_RX_N | bidir[14] / 20 / 60 | bidir[14] / 20 / 60 | 1.1+4.24=5.34 (31.6) | 1.1+4.24=5.34 (31.6) | 2.9 -> 2.9 | wired_rx -> wired_rx | none |
| WIRE_RX_P | bidir[15] / 21 / 59 | bidir[15] / 21 / 59 | 1.17+4.03=5.20 (30.7) | 1.17+4.03=5.20 (30.7) | 2.79 -> 2.79 | wired_rx -> wired_rx | xtalk partner names only |
| POR_BYPASS | bidir[16] / 22 / 58 | bidir[16] / 22 / 58 | 1.19+1.93=3.12 (18.4) | 1.19+1.93=3.12 (18.4) | 2.69 -> 2.69 | wired_aux -> strap | renamed from WCLK_IN_P; class and sparams change |
| SPARE_E17 | bidir[17] / 23 / 57 | bidir[17] / 23 / 57 | 1.06+4.15=5.21 (30.8) | 1.06+4.15=5.21 (30.8) | 2.6 -> 2.6 | wired_aux -> spare | renamed from WCLK_IN_N; class and sparams change |
| USB_DN | bidir[18] / 24 / 56 | bidir[18] / 24 / 56 | 1.22+1.96=3.18 (18.8) | 1.22+1.96=3.18 (18.8) | 2.53 -> 2.53 | debug -> usb | renamed from WCLK_OBS; class and sparams change |
| USB_DP | bidir[19] / 25 / 55 | bidir[19] / 25 / 55 | 1.12+4.29=5.41 (32.0) | 1.12+4.29=5.41 (32.0) | 2.47 -> 2.47 | debug -> usb | renamed from WDBG_OBS; class and sparams change |
| WIRE_TX_N | bidir[20] / 28 / 52 | bidir[20] / 28 / 52 | 1.06+2.08=3.14 (18.6) | 1.06+2.08=3.14 (18.6) | 2.42 -> 2.42 | wired_tx -> wired_tx | none |
| WIRE_TX_P | bidir[21] / 29 / 51 | bidir[21] / 29 / 51 | 1.11+4.05=5.16 (30.5) | 1.11+4.05=5.16 (30.5) | 2.44 -> 2.44 | wired_tx -> wired_tx | none |
| WTX_EXT_P | bidir[22] / 30 / 50 | bidir[22] / 30 / 50 | 1.12+1.92=3.04 (18.0) | 1.12+1.92=3.04 (18.0) | 2.47 -> 2.47 | wired_aux -> wired_aux | none |
| WTX_EXT_N | bidir[23] / 31 / 49 | bidir[23] / 31 / 49 | 1.04+4.08=5.12 (30.3) | 1.04+4.08=5.12 (30.3) | 2.53 -> 2.53 | wired_aux -> wired_aux | none |
| WMON | bidir[24] / 32 / 48 | bidir[24] / 32 / 48 | 1.13+2.06=3.19 (18.9) | 1.13+2.06=3.19 (18.9) | 2.6 -> 2.6 | debug -> debug | xtalk partner names only |
| TLP_TEST | bidir[25] / 33 / 47 | bidir[25] / 33 / 47 | 1.13+4.22=5.35 (31.6) | 1.13+4.22=5.35 (31.6) | 2.69 -> 2.69 | debug -> test | renamed from ESD_TEST; class and sparams change |
| H2D_D[0] | bidir[26] / 54 / 28 | bidir[26] / 38 / 43 | 2.32+4.14=6.46 (38.2) | 1.93+4.07=6.00 (35.5) | 2.79 -> 2.79 | host -> host | NORTH FIX: site kept, bond/net/contact/traces corrected |
| H2D_D[1] | bidir[27] / 53 / 29 | bidir[27] / 39 / 42 | 3.11+4.29=7.40 (43.7) | 2.53+3.73=6.26 (37.0) | 2.67 -> 2.67 | host -> host | NORTH FIX: site kept, bond/net/contact/traces corrected |
| H2D_D[2] | bidir[28] / 52 / 30 | bidir[28] / 40 / 41 | 3.5+3.94=7.44 (44.0) | 3.19+3.72=6.91 (40.8) | 2.55 -> 2.55 | host -> host | NORTH FIX: site kept, bond/net/contact/traces corrected |
| H2D_D[3] | bidir[29] / 51 / 31 | bidir[29] / 41 / 40 | 3.41+3.18=6.59 (38.9) | 3.13+2.98=6.11 (36.1) | 2.45 -> 2.45 | host -> host | NORTH FIX: site kept, bond/net/contact/traces corrected |
| H2D_D[4] | bidir[30] / 50 / 32 | bidir[30] / 42 / 39 | 3.34+2.49=5.83 (34.5) | 3.15+2.4=5.55 (32.8) | 2.36 -> 2.36 | host -> host | NORTH FIX: site kept, bond/net/contact/traces corrected |
| H2D_D[5] | bidir[31] / 49 / 33 | bidir[31] / 43 / 38 | 3.26+1.86=5.12 (30.3) | 3.13+1.81=4.94 (29.2) | 2.29 -> 2.29 | host -> host | NORTH FIX: site kept, bond/net/contact/traces corrected |
| H2D_D[6] | bidir[32] / 48 / 34 | bidir[32] / 44 / 37 | 3.16+1.17=4.33 (25.6) | 3.09+1.25=4.34 (25.6) | 2.24 -> 2.24 | host -> host | NORTH FIX: site kept, bond/net/contact/traces corrected |
| H2D_D[7] | bidir[33] / 47 / 35 | bidir[33] / 45 / 36 | 2.2+0.71=2.91 (17.2) | 2.22+0.66=2.88 (17.0) | 2.21 -> 2.21 | host -> host | NORTH FIX: site kept, bond/net/contact/traces corrected |
| H2D_CLK | bidir[34] / 45 / 36 | bidir[34] / 47 / 35 | 2.22+0.66=2.88 (17.0) | 2.2+0.71=2.91 (17.2) | 2.21 -> 2.21 | host -> host | NORTH FIX: site kept, bond/net/contact/traces corrected |
| H2D_D[8] | bidir[35] / 44 / 37 | bidir[35] / 48 / 34 | 3.09+1.25=4.34 (25.6) | 3.16+1.17=4.33 (25.6) | 2.24 -> 2.24 | host -> host | NORTH FIX: site kept, bond/net/contact/traces corrected |
| H2D_D[9] | bidir[36] / 43 / 38 | bidir[36] / 49 / 33 | 3.13+1.81=4.94 (29.2) | 3.26+1.86=5.12 (30.3) | 2.29 -> 2.29 | host -> host | NORTH FIX: site kept, bond/net/contact/traces corrected |
| CLK_OBS | bidir[37] / 42 / 39 | bidir[37] / 50 / 32 | 3.15+2.4=5.55 (32.8) | 3.34+2.49=5.83 (34.5) | 2.36 -> 2.36 | debug -> debug | NORTH FIX: site kept, bond/net/contact/traces corrected |
| DBG_OBS0 | bidir[38] / 41 / 40 | bidir[38] / 51 / 31 | 3.13+2.98=6.11 (36.1) | 3.41+3.18=6.59 (38.9) | 2.45 -> 2.45 | debug -> debug | NORTH FIX: site kept, bond/net/contact/traces corrected |
| DBG_OBS1 | bidir[39] / 40 / 41 | bidir[39] / 52 / 30 | 3.19+3.72=6.91 (40.8) | 3.5+3.94=7.44 (44.0) | 2.55 -> 2.55 | debug -> debug | NORTH FIX: site kept, bond/net/contact/traces corrected |
| ATB0 | analog[0] / 39 / 42 | analog[0] / 53 / 29 | 2.53+3.73=6.26 (37.0) | 3.11+4.29=7.40 (43.7) | 2.67 -> 2.67 | debug -> debug | NORTH FIX: site kept, bond/net/contact/traces corrected |
| ATB1 | analog[1] / 38 / 43 | analog[1] / 54 / 28 | 1.93+4.07=6.00 (35.5) | 2.32+4.14=6.46 (38.2) | 2.79 -> 2.79 | debug -> debug | NORTH FIX: site kept, bond/net/contact/traces corrected |
| RF_TX_N | inputs[2] / 59 / 23 | inputs[0] / 55 / 27 | 1.15+1.91=3.06 (18.1) | 1.18+4.21=5.39 (31.9) | 2.69 -> 3.16 | rf_tx -> rf_tx | site moved (map) |
| RF_TX_P | inputs[3] / 60 / 22 | inputs[1] / 56 / 26 | 1.22+1.9=3.12 (18.4) | 1.33+4.35=5.68 (33.6) | 2.6 -> 3.02 | rf_tx -> rf_tx | site moved (map) |
| REF_IN_N | inputs[6] / 65 / 17 | inputs[2] / 59 / 23 | 1.41+4.25=5.66 (33.5) | 1.15+1.91=3.06 (18.1) | 2.42 -> 2.69 | lo_ref -> lo_ref | site moved (map) |
| REF_IN | inputs[7] / 66 / 16 | inputs[3] / 60 / 22 | 1.2+1.98=3.18 (18.8) | 1.22+1.9=3.12 (18.4) | 2.44 -> 2.6 | lo_ref -> lo_ref | site moved (map) |
| AUX_CLK_N | inputs[4] / 61 / 21 | inputs[4] / 61 / 21 | 1.22+4.24=5.46 (32.3) | 1.22+4.24=5.46 (32.3) | 2.53 -> 2.53 | lo_ref -> lo_ref | xtalk partner names only |
| AUX_CLK_P | inputs[5] / 62 / 20 | inputs[5] / 62 / 20 | 1.05+4.17=5.22 (30.9) | 1.05+4.17=5.22 (30.9) | 2.47 -> 2.47 | lo_ref -> lo_ref | none |
| BB_Q_N | inputs[0] / 55 / 27 | inputs[6] / 65 / 17 | 1.18+4.21=5.39 (31.9) | 1.41+4.25=5.66 (33.5) | 3.16 -> 2.42 | debug -> debug | site moved (map) |
| BB_Q_P | inputs[1] / 56 / 26 | inputs[7] / 66 / 16 | 1.33+4.35=5.68 (33.6) | 1.2+1.98=3.18 (18.8) | 3.02 -> 2.44 | debug -> debug | site moved (map) |
| BB_I_N | inputs[8] / 67 / 15 | inputs[8] / 67 / 15 | 1.06+4.03=5.09 (30.1) | 1.06+4.03=5.09 (30.1) | 2.47 -> 2.47 | debug -> debug | xtalk partner names only |
| BB_I_P | inputs[9] / 68 / 14 | inputs[9] / 68 / 14 | 1.24+2.13=3.37 (19.9) | 1.24+2.13=3.37 (19.9) | 2.53 -> 2.53 | debug -> debug | none |
| RF_RX_N | inputs[10] / 69 / 13 | inputs[10] / 69 / 13 | 1.33+4.68=6.01 (35.5) | 1.33+4.68=6.01 (35.5) | 2.6 -> 2.6 | rf_rx -> rf_rx | none |
| RF_RX_P | inputs[11] / 70 / 12 | inputs[11] / 70 / 12 | 0.9+4.07=4.97 (29.4) | 0.9+4.07=4.97 (29.4) | 2.69 -> 2.69 | rf_rx -> rf_rx | none |
