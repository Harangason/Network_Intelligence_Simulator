# Validation And Findings

Relevant finding vocabulary:

- `HARDWARE_INTERFACE_MISSING`
- `HARDWARE_CAPABILITY_EXCEEDED`
- `INTERFACE_NETWORK_UNMAPPED`
- `MESSAGE_INTERFACE_UNMAPPED`
- `FUNCTION_INTERFACE_TRANSPORT_UNMAPPED`
- `NETWORK_CAPACITY_EXCEEDED`

`HardwareInterfaceAllocationService` emits `HARDWARE_CAPABILITY_EXCEEDED` when allocation would exceed supported technologies or channel limits.
