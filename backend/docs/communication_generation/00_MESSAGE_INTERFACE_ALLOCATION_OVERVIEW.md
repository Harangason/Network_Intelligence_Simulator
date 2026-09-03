# Message / Interface Allocation Overview

As-built rule:

```text
Signals fill Messages.
Messages consume bus time.
Interfaces connect Hardware to Networks.
Networks provide communication capacity.
```

Compatible signals are packed into messages by producer, sender hardware, technology, timing, receiver set and priority. Packed messages are allocated to sender interfaces with a reuse-first policy until the configured projected load threshold is reached.
