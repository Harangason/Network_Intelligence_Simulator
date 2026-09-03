# Wizard Integration

The project wizard prompt keeps the required order:

```text
Functions -> Functional Interfaces -> Signals -> Messages -> Hardware Mapping -> Hardware Interface Allocation -> Bus Load -> Routing
```

The frontend wizard is presentation and orchestration only. Deterministic packing, allocation and capacity rules live in Python.
