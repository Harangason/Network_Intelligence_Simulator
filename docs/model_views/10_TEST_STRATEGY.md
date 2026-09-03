# Test Strategy

Covered by unit checks:

- CAN-FD payload class selection
- packing before allocation
- reuse of one interface for multiple Messages
- capability-limit blocking
- same-network interfaces do not double network capacity

Recommended integration checks use the Engineering API to create Hardware, Hardware Interface, Function, Interface, Message and Signal, then verify relations and view loading.
