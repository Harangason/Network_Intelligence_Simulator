# Architecture Compliance

A change is compliant when:

- Large data stays in backend persistence or artifact storage.
- Frontend state contains projections and selected details only.
- Caches have namespace, owner, max entries, max bytes and eviction policy.
- List endpoints avoid full nested payloads.
- Renderers use stable dimensions and bounded windows.
- Tests cover the policy contract when a new cache or large endpoint is added.

