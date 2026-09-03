# Interface Allocation

Allocation policy:

```text
REUSE_EXISTING_CAPACITY_FIRST
```

Messages are allocated to a sender hardware / technology channel. The projected message load is added to the current channel load. A new channel is selected only when the configured target load would be exceeded.
