# Hardware Capabilities

Hardware capabilities are deterministic Python inputs for allocation.

The allocation model supports:

- `supported_network_technologies`
- per-technology maximum channel counts
- reuse of existing physical capacity before proposing a new channel

The UI displays capability-related fields on `HardwareNetworkInterface`; hardware-node capability enrichment remains part of the generator and allocation service inputs.
