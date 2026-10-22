"""Shared bounded sizes for complete source-bound engineering requests."""
MAX_DOCUMENT_SOURCE_CHARS = 1_000_000
# Original text, reviewed source snapshot, bounded typed evidence and choices.
# This bounds storage/transport; individual inference context budgets remain.
MAX_REQUIREMENT_LENGTH = 4 * MAX_DOCUMENT_SOURCE_CHARS + 100_000
MAX_REQUIREMENT_REQUEST_BYTES = 12 * MAX_REQUIREMENT_LENGTH + 1_048_576
