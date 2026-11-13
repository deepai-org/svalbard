#!/bin/bash
# top-level fill with keep-outs: ko_chain.sh  (sequential, 1 heavy job at a time)
cd /home/ubuntu/svalbard/scratch/integration/signoff-gap/fill
ALL='^(adc_[iq]|aosc|bb_tap|bbfilter_[iq]|cdr|clk_obs|clockmux|core_bias|ctle|dac_[iq]|detect|diff_clk_rx|hsbias|lna|lo_ext|pll_ring|polyphase|por|prescale|refbuf|rfdriver|ring_osc|rxlevel|rxmix_[iq]|rxselect|slicer|termination|txmix_[iq]|txsum|vco_replica|wiredtx|wmon_sel|wordclk)$'
RF='^(lna|rxmix_[iq]|lo_ext|polyphase|pll_ring|vco_replica|aosc|ring_osc|txmix_[iq]|txsum|rfdriver)$'
for s in rf all; do
  [ $s = all ] && P="$ALL" || P="$RF"
  ./kl.sh keepout.py -rd gds=/repo/scratch/chip-assembly-dev/pt_chip_top.gds -rd out=/h/out/top_ko_$s.oas -rd "pat='$P'" > out/top_ko_$s.keepout.json
  ./run_fill.sh out/top_ko_$s.oas top_ko_$s.fill.oas 2
  ./kl.sh dens.py -rd gds=/h/out/top_ko_$s.fill.oas -rd out=/h/out/top_ko_$s.dens.json
  rm -f out/top_ko_$s.oas out/top_ko_$s.fill.oas
done
echo KODONE
