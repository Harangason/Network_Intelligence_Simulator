# Test Strategy

Implemented tests:

- `frontend/src/lib/agent/engineering-specification.test.mjs`: wizard packing, message reuse, CAN-FD classes and atomic split behavior.
- `backend/tests/test_message_packing.py`: CAN-FD DLC table, producer/timing/receiver grouping, atomic message split and reuse-first interface allocation.

Regression focus:

- No one-message-per-interface rule.
- No signal split across two messages.
- Legal CAN-FD payload classes.
- Interface allocation by projected load, not message count.
