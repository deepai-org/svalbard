# Complete Gigabit Ethernet port

Build a full-duplex 1000BASE-X-style Ethernet port on GF180MCU. One integrated
design must carry frames from the host TX stream through a 1.25-GBd serial PHY
and recover frames from the serial RX pins back to the host. The deliverable
includes the MAC, PCS, PMA, CDR, analog front end, mapped logic, and final GDS.

This is a whole-port challenge. Disconnected sub-blocks do not pass. T7 requires
packet-to-pins-to-packet operation from the routed, extracted design across every
mandatory test case.

The package supplies the fixed interfaces, numerical contract, GF180MCU process
lock, independent reference oracles, 42-requirement coverage ledger, hard gates,
and tiered score. The participant supplies the design.

```sh
make selftest
make visible OUTPUT=/app/output  # with a candidate
```

`selftest` checks CRC/frame behavior, the complete 8b/10b and ordered-set oracle,
analog metrics, coverage closure, evidence rejection, and starter syntax. The
starter compiles and fails the functional test, as a starter should.

All 42 requirements map to 17 concrete test scenarios, and every local oracle
passes its self-test. The public release gate is to implement the remaining
candidate adapters and run one end-to-end pilot that freezes runtime and score
thresholds.
