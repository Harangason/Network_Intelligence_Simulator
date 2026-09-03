# Interface Model Overview

The simulator separates logical functional interfaces from physical hardware interfaces.

Canonical chain:

```text
Function -> Interface -> Message -> HardwareNetworkInterface -> Network / Bus
```

`Interface` remains the logical view of data and service exposure. `HardwareNetworkInterface` is the physical communication controller, channel or port owned by a `HardwareNode`.
