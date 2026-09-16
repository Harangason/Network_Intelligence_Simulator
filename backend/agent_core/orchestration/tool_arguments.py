"""Validate model-generated business arguments before any tool side effect."""
from __future__ import annotations

import json
from jsonschema import Draft202012Validator


def prepare_arguments(value, schema):
    """Decode only JSON where the schema unambiguously expects non-string data.

    No eval, guessed IDs, enum aliases, missing defaults or invented fields.
    The authoritative MCP/domain validators still run afterwards.
    """
    def normalize(item, rule):
        branches = rule.get('anyOf') or rule.get('oneOf') or [rule]
        types = {t for branch in branches for t in
                 (branch.get('type', []) if isinstance(branch.get('type'), list) else [branch.get('type')])}
        if isinstance(item, str) and 'string' not in types and types & {'object', 'array', 'null', 'number', 'integer', 'boolean'}:
            try:
                item = json.loads(item)
            except (ValueError, TypeError):
                pass  # Report a precise schema error, never evaluate Python text.
        selected = next((branch for branch in branches
                         if (isinstance(item, dict) and branch.get('type') == 'object')
                         or (isinstance(item, list) and branch.get('type') == 'array')), rule)
        if isinstance(item, dict):
            properties = selected.get('properties', {})
            extra = selected.get('additionalProperties', {})
            return {key: normalize(child, properties.get(key, extra if isinstance(extra, dict) else {}))
                    for key, child in item.items()}
        if isinstance(item, list):
            return [normalize(child, selected.get('items', {})) for child in item]
        return item

    result = normalize(value, schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(result), key=lambda error: str(list(error.path)))
    if errors:
        error = errors[0]
        path = '.'.join(str(part) for part in error.path) or 'arguments'
        # Do not echo arbitrary argument contents (requirements may be large).
        raise ValueError(f'{path}: violates {error.validator}; expected {error.validator_value!r}.')

    def identifiers(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if (key == 'id' or key.endswith('_id')) and isinstance(child, str) and child.strip().lower() in {'null', 'none', 'undefined', ''}:
                    raise ValueError(f'{key}: a placeholder is not an identifier. Use a real reference or schema-permitted null.')
                identifiers(child)
        elif isinstance(item, list):
            for child in item:
                identifiers(child)
    identifiers(result)
    return result
