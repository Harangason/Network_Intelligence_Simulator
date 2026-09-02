# Fault Injection

Die bestehende `FaultInjectionEngine` bleibt massgeblich.

Reihenfolge:

1. Golden Behavior
2. Constraints / Rate Limits
3. Noise
4. Fault Injection
5. Encoding
6. Trace

Faults veraendern den Actual Value, waehrend `golden_value` vergleichbar bleibt.

