# Trace And QA

Signal architecture changes are verified across parser, generator, audit and UI.

Quality checks:

- imported signals preserve semantic tables.
- generated signals include canonical layers.
- legacy unknown signals are not auto-optimised.
- Capacity warnings identify their origin.
- repeated wizard generation keeps data quality deviation at or below the accepted threshold.

Regression tests should include DBC value tables, state signals, boolean flags, counters, bitfields and incomplete legacy signals.
