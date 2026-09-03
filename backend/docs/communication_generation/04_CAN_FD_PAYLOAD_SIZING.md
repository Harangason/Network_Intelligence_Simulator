# CAN-FD Payload Sizing

Supported CAN-FD payload classes:

```text
0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64 Byte
```

The default policy is `MINIMUM_VALID_SIZE`: choose the smallest legal class that can contain the packed signal bits.
