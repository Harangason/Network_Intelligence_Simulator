"""Typed, source-bound draft methods. Structural validity is not risk acceptance."""
from copy import deepcopy
from itertools import product
import json
import re

SCHEMA = "eip.assurance-draft.v1"
METHODS = {"fmea": "safety", "fta": "safety", "stride": "security", "attack-tree": "security", "nis-evidence": "safety", "nis-security-evidence": "security"}
STRIDE = ("spoofing", "tampering", "repudiation", "information-disclosure", "denial-of-service", "elevation-of-privilege")


def _text(value, field, *, required=True, maximum=2000):
    if value is None and not required:
        return ""
    if not isinstance(value, str) or len(value) > maximum or required and not value.strip():
        raise ValueError(f"{field}: bounded {'nonempty ' if required else ''}text required")
    return value.strip()


def _fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError("Unsupported or missing analysis fields")


def _rows(value, *, maximum=64):
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        raise ValueError(f"Between 1 and {maximum} entries required")
    return value


def _source(value, sources):
    ref = _text(value, "sourceRef", maximum=200)
    if ref not in sources:
        raise ValueError("Every sourceRef requires an explicit original source revision")
    return ref


def evaluate(method, analysis, sources):
    """Evaluate explicit analyst input only; never infer causes or likelihoods."""
    if not isinstance(method, str) or method not in METHODS:
        raise ValueError("Unsupported assurance method")
    gaps, used = [], set()
    if method in {"nis-evidence", "nis-security-evidence"}:
        from core.nis_assurance import evaluate_nis
        imported = evaluate_nis(analysis, sources)
        result, gaps, used = imported["result"], imported["gaps"], set(sources)
    elif method == "fmea":
        _fields(analysis, {"rows"}, {"rows"})
        rows = []
        for index, row in enumerate(_rows(analysis["rows"])):
            _fields(row, {"sourceRef", "failureMode", "cause", "localEffect", "systemEffect", "detection", "controls", "severity", "occurrence", "detectability"}, {"sourceRef", "failureMode"})
            source = _source(row["sourceRef"], sources); used.add(source)
            normalized = {"sourceRef": source, "failureMode": _text(row["failureMode"], "failureMode")}
            for field in ("cause", "localEffect", "systemEffect", "detection", "controls"):
                normalized[field] = _text(row.get(field), field, required=False)
                if not normalized[field]: gaps.append(f"row:{index + 1}:{field}_missing")
            for field in ("severity", "occurrence", "detectability"):
                score = row.get(field)
                if score is not None and (type(score) is not int or not 1 <= score <= 10):
                    raise ValueError(f"{field}: explicit local integer score 1–10 or null required")
                normalized[field] = score
                if score is None: gaps.append(f"row:{index + 1}:{field}_unassessed")
            normalized["rpn"] = (normalized["severity"] * normalized["occurrence"] * normalized["detectability"]
                if all(normalized[field] is not None for field in ("severity", "occurrence", "detectability")) else None)
            rows.append(normalized)
        result = {"rows": rows, "ratingScale": "Explicit local 1–10 S/O/D; RPN=S*O*D; no normative acceptance threshold"}
    elif method == "stride":
        _fields(analysis, {"entries"}, {"entries"})
        entries, covered = [], set()
        for index, row in enumerate(_rows(analysis["entries"])):
            _fields(row, {"sourceRef", "category", "scenario", "mitigation"}, {"sourceRef", "category", "scenario"})
            source = _source(row["sourceRef"], sources); used.add(source)
            if row["category"] not in STRIDE: raise ValueError("Unknown STRIDE category")
            covered.add(row["category"])
            mitigation = _text(row.get("mitigation"), "mitigation", required=False)
            if not mitigation: gaps.append(f"entry:{index + 1}:mitigation_missing")
            entries.append({"sourceRef": source, "category": row["category"],
                "scenario": _text(row["scenario"], "scenario"), "mitigation": mitigation})
        missing = sorted(set(STRIDE) - covered)
        gaps.extend(f"category:{category}:not_assessed" for category in missing)
        result = {"entries": entries, "assessedCategories": sorted(covered), "unassessedCategories": missing}
    else:
        _fields(analysis, {"rootId", "nodes"}, {"rootId", "nodes"})
        nodes = {}
        for node in _rows(analysis["nodes"]):
            _fields(node, {"id", "label", "kind", "children", "sourceRef"}, {"id", "label", "kind"})
            key = _text(node["id"], "node id", maximum=64)
            if key in nodes: raise ValueError("Duplicate tree node")
            kind = node["kind"]
            if not isinstance(kind, str) or kind not in {"event", "and", "or"}: raise ValueError("Tree kind must be event, and or or")
            normalized = {"id": key, "label": _text(node["label"], "label"), "kind": kind}
            if kind == "event":
                if node.get("children"): raise ValueError("Basic events cannot have children")
                source = _source(node.get("sourceRef"), sources); used.add(source)
                normalized["sourceRef"] = source
            else:
                children = _rows(node.get("children"), maximum=16)
                if len(children) < 2 or any(not isinstance(child, str) for child in children) or len(set(children)) != len(children):
                    raise ValueError("AND/OR requires at least two distinct child IDs")
                if node.get("sourceRef"): raise ValueError("Gate sources belong to their explicit basic events")
                normalized["children"] = children
            nodes[key] = normalized
        root = _text(analysis["rootId"], "rootId", maximum=64)
        visited, active, cache = set(), set(), {}
        budget = [0]
        def visit(key):
            if key not in nodes: raise ValueError("Unknown tree child/root")
            if key in active: raise ValueError("Cyclic tree")
            if key in cache: return cache[key]
            active.add(key); visited.add(key)
            node = nodes[key]
            if node["kind"] == "event": sets = {frozenset({key})}
            else:
                branches = [visit(child) for child in node["children"]]
                sets = set()
                candidates = ((part,) for branch in branches for part in branch) if node["kind"] == "or" else product(*branches)
                for parts in candidates:
                    budget[0] += 1
                    if budget[0] > 4096: raise ValueError("Qualitative evaluation exceeds 4096 combinations; split the model")
                    candidate = frozenset().union(*parts)
                    if not any(existing <= candidate for existing in sets):
                        sets = {existing for existing in sets if not candidate < existing}
                        sets.add(candidate)
                    if len(sets) > 256: raise ValueError("Qualitative result exceeds 256 sets; split the model")
            active.remove(key); cache[key] = sets
            return sets
        minimal = visit(root)
        if visited != set(nodes): raise ValueError("Unreachable tree nodes")
        result = {"rootId": root, "nodes": list(nodes.values()),
            "minimalCutSets" if method == "fta" else "minimalAttackSets": sorted([sorted(part) for part in minimal]),
            "quantitativeProbability": None, "evaluationScope": "Qualitative explicit AND/OR logic only"}
        gaps.append("quantitative_probability_not_assessed")
    if used != set(sources): raise ValueError("Source revision map must match the sources actually cited")
    return {"method": method, "schemaVersion": SCHEMA, "result": result, "gaps": gaps,
        "status": "draft", "reviewRequired": True, "releaseApproved": False, "riskAcceptance": "not_assessed"}


def save_draft(project_id, payload, context, *, expected_revision, repository=None, auth_db_factory=None):
    from core.persistence.change_control import require_actor, is_protected
    from core.persistence.repository import ProfessionalRepository, CommandContext, PersistenceConflict, RevisionRequired, ObjectNotFound, request_hash
    if not isinstance(context, CommandContext) or not context.idempotency_key:
        raise RevisionRequired("Authenticated command context and Idempotency-Key required")
    require_actor(project_id, context.actor_id, auth_db_factory=auth_db_factory)
    _fields(payload, {"id", "title", "method", "sourceRevisions", "analysis", "reason"}, {"id", "title", "method", "sourceRevisions", "analysis", "reason"})
    if len(json.dumps(payload, allow_nan=False)) > (2097152 if payload.get("method") in {"nis-evidence", "nis-security-evidence"} else 65536): raise ValueError("Analysis exceeds its bounded import size")
    if type(expected_revision) is not int or expected_revision < 0: raise RevisionRequired("Original analysis revision required; zero for new draft")
    key = _text(payload["id"], "id", maximum=200)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", key): raise ValueError("Stable analysis reference required")
    title, reason = _text(payload["title"], "title", maximum=300), _text(payload["reason"], "reason")
    sources = payload["sourceRevisions"]
    if not isinstance(sources, dict) or not 1 <= len(sources) <= 20 or any(not isinstance(ref, str) or type(rev) is not int or rev < 1 for ref, rev in sources.items()):
        raise ValueError("1–20 source references with original positive revisions required")
    evaluated = evaluate(payload["method"], payload["analysis"], sources)
    if payload["method"] in {"nis-evidence", "nis-security-evidence"} and payload["analysis"]["eipProjectId"] != project_id:
        raise ValueError("Mapped EIP project differs from authenticated command project")
    repo = repository or ProfessionalRepository()
    digest = request_hash({"payload": payload, "expectedRevision": expected_revision})
    with repo.engine.begin() as connection:
        project = repo._project(connection, project_id, lock=True)
        replay = repo._reserve_or_replay(connection, project["id"], context, digest, "assurance.draft.save")
        if replay is not None: return {**replay, "idempotentReplay": True}
        old = repo.object_by_key(project_id, key, connection=connection, lock=True)
        if old:
            if old["object_type"] != "AssuranceAnalysis" or is_protected(old) or old["status"] != "draft":
                raise PersistenceConflict("Only an existing unapproved analysis draft can be edited")
            repo._check_revision(old["revision"], expected_revision)
        elif expected_revision != 0: raise ObjectNotFound("Original analysis no longer exists")
        for ref, revision in sorted(sources.items()):
            row = repo.object_by_key(project_id, ref, connection=connection, lock=True)
            if not row or row.get("status") in {"archived", "inactive", "deleted"} or row.get("lifecycle_status") in {"archived", "inactive", "deleted"}:
                raise ObjectNotFound("Active source missing from this project")
            if row["object_type"] == "AssuranceAnalysis": raise ValueError("Nested analyses require an explicit dependency contract")
            repo._check_revision(row["revision"], revision)
            if payload["method"] in {"nis-evidence", "nis-security-evidence"} and any(item["sourceRef"] == ref for item in evaluated["result"]["requirements"]) and row["object_type"] != ("SafetyRequirement" if METHODS[payload["method"]] == "safety" else "SecurityRequirement"):
                raise ValueError("NIS requirements must bind canonical Core safety/security requirement objects")
        metadata = {"schemaVersion": SCHEMA, "method": payload["method"], "domain": METHODS[payload["method"]],
            "sourceRevisions": deepcopy(sources), "analysis": deepcopy(payload["analysis"]), "assessment": evaluated,
            "reason": reason, "reviewRequired": True, "releaseApproved": False}
        saved = repo.upsert_engineering_object(project_id, key, "AssuranceAnalysis", title, status="draft", metadata=metadata,
            context=CommandContext(context.actor_id, context.correlation_id, context.idempotency_key + ":object"),
            expected_revision=expected_revision, connection=connection)
        response = {"ok": True, "atomic": True, "projectId": project_id, "id": key, "revision": saved["revision"],
            "record": {"id": key, "ref": key, "revision": saved["revision"]},
            "assessment": evaluated, "sourceRevisions": sources, "coreWritesPerformed": True, "releaseApproved": False}
        repo._complete_idempotency(connection, project["id"], context, digest, "assurance.draft.save", response)
        return response
