from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Callable, Iterable, Mapping


def normalize_identity(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text)


class DuplicateValidator:
    def __init__(
        self,
        *,
        aliases: Mapping[str, str] | None = None,
        semantic_key: Callable[[Mapping[str, Any]], str] | None = None,
        near_threshold: float = 0.9,
    ) -> None:
        self.aliases = {normalize_identity(key): value for key, value in (aliases or {}).items()}
        self.semantic_key = semantic_key
        self.near_threshold = near_threshold

    def _semantic(self, item: Mapping[str, Any]) -> str:
        if self.semantic_key:
            return normalize_identity(self.semantic_key(item))
        name = normalize_identity(item.get("name"))
        semantic = item.get("semantic") or {}
        concept = normalize_identity(semantic.get("concept") if isinstance(semantic, Mapping) else "")
        return self.aliases.get(concept or name, concept or name)

    def validate(self, objects: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        identifiers: dict[str, str] = {}
        names: dict[str, str] = {}
        semantics: dict[str, str] = {}
        known_names: list[tuple[str, str]] = []
        for index, item in enumerate(objects):
            object_ref = str(item.get("workload_object_id") or item.get("id") or index)
            definition = item.get("definition") if isinstance(item.get("definition"), Mapping) else item
            identifier = normalize_identity(definition.get("id"))
            name = normalize_identity(definition.get("name"))
            semantic = self._semantic(definition)
            if identifier and identifier in identifiers:
                findings.append({"code": "DUPLICATE_ID", "severity": "ERROR", "object": object_ref, "duplicate_of": identifiers[identifier]})
            elif name and name in names:
                findings.append({"code": "DUPLICATE_NAME", "severity": "ERROR", "object": object_ref, "duplicate_of": names[name]})
            elif semantic and semantic in semantics:
                findings.append({"code": "POSSIBLE_DUPLICATE", "severity": "WARNING", "object": object_ref, "duplicate_of": semantics[semantic]})
            else:
                near = next(
                    (
                        reference
                        for known_name, reference in known_names
                        if name and SequenceMatcher(None, name, known_name).ratio() >= self.near_threshold
                    ),
                    None,
                )
                if near:
                    findings.append({"code": "NEAR_DUPLICATE", "severity": "WARNING", "object": object_ref, "duplicate_of": near})
            if identifier:
                identifiers.setdefault(identifier, object_ref)
            if name:
                names.setdefault(name, object_ref)
                known_names.append((name, object_ref))
            if semantic:
                semantics.setdefault(semantic, object_ref)
        return findings
