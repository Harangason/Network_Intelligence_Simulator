# Technology parameter repair
Approved by user: Freigabe, 2026-10-01.
Current project 20261001051525213-c260002f has confirmed I2C bitrate=100000. Four proposal interface findings request opaque local_timing_evidence.
Root causes: independent frontend minimum-rate policy vs schema historical rate vs wizard review policy; I2C schema has no default and local review proposes historical 400000; SPI wizard erroneously proposes device-dependent historical 50000000; schema labels inherited CAN rate Ethernet; validator ignores minimum; NMEA2000 no fixed-rate constraint; capacity uses separate alias list; source parameter overlay on primary switch leaks rates; proposal hides individual hardware requirements.
All catalog entries will be audited, review suggestions remain distinct from actual confirmed transaction/device proof. No invented device evidence or complete timing model for unsupported catalog entries.
Existing profile declared-parameter tests and technology parameter review E2E extended; campaign stays REPAIR_1_ACTIVE without claiming full campaign PASS.
