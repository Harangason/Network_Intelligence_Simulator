# Message Interface Allocation

Message allocation happens after message packing.

Python module:

```text
backend/engineering/message_packing.py
```

`HardwareInterfaceAllocationService` assigns packed Messages to physical interfaces with reuse-first behavior and capability checks.
