"""Structural invariants that protect technology ownership and import identity."""
import ast
import importlib
from pathlib import Path

from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
from backend.nis.communication.catalog import technology_definitions
from backend.nis.compatibility import ALIASES

ROOT = Path(__file__).resolve().parents[2]


def test_every_runtime_profile_has_one_definition_owner():
    definitions = technology_definitions()
    ids = [profile["id"] for profile in definitions]
    assert len(ids) == len(set(ids)) == 125
    assert {profile["id"] for profile in DEFAULT_TECHNOLOGY_REGISTRY.list_all()} == set(ids)
    for key in ids:
        module = importlib.import_module(f"backend.nis.communication.technologies.{key}.definition")
        assert Path(module.__file__).parent.name == key
        assert module.PROFILE["id"] == key


def test_old_registry_and_class_imports_preserve_singleton_identity():
    pairs = [
        ("backend.communication.technologies", "backend.nis.communication"),
        ("backend.communication.technologies.models", "backend.nis.communication.core.models"),
        ("backend.app", "backend.nis.app"),
        ("backend.agent_core.runtime.executor", "backend.nis.agent.runtime.executor"),
        ("agent_core.errors", "backend.nis.agent.errors"),
        ("agent_core.core.workload", "backend.nis.agent.core.workload"),
        ("communication.technologies.models", "backend.nis.communication.core.models"),
        ("common_trace", "backend.nis.traces.formats.common_trace"),
    ]
    for old, canonical in pairs:
        if old in ALIASES:
            assert importlib.import_module(old) is importlib.import_module(canonical)


def test_canonical_imports_do_not_return_to_legacy_owners():
    violations = []
    for source in (ROOT / "backend/nis").rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8-sig"))):
            modules = ([node.module] if isinstance(node, ast.ImportFrom) and node.level == 0
                       else [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            for module in modules:
                if module in ALIASES:
                    violations.append((source.relative_to(ROOT).as_posix(), node.lineno, module))
    assert not violations


def test_industry_templates_reference_profile_owners():
    for source in (ROOT / "backend/nis/industries").glob("*/templates/generators/technology_generator.py"):
        tree = ast.parse(source.read_text())
        assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == "legacy_profiles" for node in ast.walk(tree))
        assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                       and node.func.id == "p" for node in ast.walk(tree))


def test_frontend_vocabulary_is_an_exact_domain_projection():
    import json
    owner = ROOT / "backend/nis/domain/inventory-vocabulary.json"
    projection = ROOT / "frontend/src/features/agent/lib/inventory-vocabulary.json"
    assert json.loads(owner.read_text(encoding="utf-8")) == json.loads(projection.read_text(encoding="utf-8"))
