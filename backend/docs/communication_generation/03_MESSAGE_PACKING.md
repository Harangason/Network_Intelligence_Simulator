# Message Packing

Packing is deterministic and atomically places each signal into exactly one payload region. A message is filled while another compatible signal fits within the technology-specific maximum payload. When it does not fit, a new message is created for the same group.

Persisted metadata includes used bits, capacity bits, free bits, utilization and projected load.
