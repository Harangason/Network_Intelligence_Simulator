# Tests

The governance tests validate:

- Required memory/cache/rendering inventory layers exist.
- Cache policies are bounded.
- TTL policies have positive TTLs.
- Memory budgets have soft and hard limits.
- Oversized payloads are rejected by the budget assertion helper.

Test file:

- `backend/tests/test_performance_governance.py`

