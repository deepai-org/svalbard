# Declared thresholds (written 2026-11-19 BEFORE any full-coverage extraction result was looked at)

Extraction: Magic extresist (analog image tools.ANALOG_IMAGE, same recipe as extract_rc / s13 rc.py) on the flattened
cell with `extresist tolerance 0` + `extresist simplify off` (first try, tolerance 0.001 with simplify on, output R for only 5-10 % of nets and was discarded before auditing), VDD/VSS/VSUBS ignored.

Per net (every non-supply net that is NOT in the cell's drawn-R netlist *.rc.spice):
* R_series = max over load nodes (gate terminals, cell ports) of min over driver nodes (FET drain/source terminals) of the
  shortest-path resistance through the net's extracted resistor graph (series sum along the lowest-R path; >= the true
  effective resistance -> conservative).  Nets with no FET drain/source (port-driven inputs): driver = the port node;
  if neither, max pairwise shortest-path R over all terminal nodes.
* Ron model (driver): Ron = K * (L/0.28um) / W[um], K_n = 2.0 kOhm*um, K_p = 4.5 kOhm*um (GF180 3.3 V, ~ VDD / (2*Idsat)
  linear-equivalent switching resistance).  Driver Ron of the net = MIN Ron over all FETs whose drain or source touches the
  net (strongest driver -> strictest threshold).  Nets with no FET D/S: Ron undefined, criterion (a) not applicable.
* C_net = sum of all capacitors touching the net in the cell's *.ext.spice (ground + coupling), names matched with '/'=='.'.

Criteria:
* (a) R_series < 0.05 * Ron_driver
* (b) R_series * C_net < 2 ps
* Timing nets: last hierarchy component (after the last '.' or '/', '#...' suffix dropped) matches
  `^(PH|PS)\w*$|^(CK|CLK)\w*$|^Q\d+$|^F\d+$|^STR\w*$|^(MAIN|POST)_[PN]$|^TAIL\w*$|^(XT|AP|AN)[MQ]?$|^X$|^(BM|BQ)\d+$`
  (phases, register clocks, F/stream nets, output buses, tails, CML gate-line trunks): PASS only if (b).
* All other nets: PASS if (a) or (b).
* FAIL otherwise -> listed (name, R, C, driver, why it matters).  Supplies (VDD*, VSS*, VSUBS) are excluded.

Negative control: >= 3 nets that ARE in the drawn-R netlists: extractor R_series vs drawn lumped R, PASS if within 30 %.

## Amendments (made after the first audit pass; thresholds themselves unchanged)
* Extraction: first pass with tolerance 0.001 / simplify on output R for only 5-10 % of nets -> rerun with tolerance 0 and
  `extresist simplify off` (all audit results come from the rerun).
* C_net: unnamed flattened nets (a_x_y#) are not name-matchable to *.ext.spice (~50 % of nets had no match, which made
  criterion (b) pass trivially).  C_net = max(C in *.ext.spice, C of the same net in this full extraction, cthresh 0).
