# Wizard input whitespace defect

User reports on iPhone via 192.168.178.10 that the project-description field cannot accept spaces. Attached screenshot shows concatenated words.

Root cause: agent-chat-core.tsx project's controlled textarea trims the rendered value and also requirement.trim() on every input event. Typing a space after a word removes that space immediately; the next word is concatenated. This is deterministic from the source, independent of VLAN transport. No executed reproduction or tests were performed because the user's no-test instruction remains active.

Owner PROJECT_PRODUCT, first failing layer controlled frontend textarea. Repair preserves raw description whitespace in state/rendering/sessionStorage while stripping only internal reviewed-choice metadata and its delimiter. Existing submission validation may still trim for empty-input checking and confirmed request construction. This does not alter wizard ownership, review decisions, bindings, industry selection or operation revisions.
