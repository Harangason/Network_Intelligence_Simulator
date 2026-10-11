"""Typed Safety/Security context plus explicitly assistive HARA/TARA output."""
from core.collaboration_projection import _evidence, _mappings, permissions, verification_snapshot
from core.collaboration_workflow import _active, _metadata
from core.readiness_projection import currently_approved
from core.verification.assessment import assess_verification

SAFETY = {"Hazard", "SafetyRisk", "SafetyGoal", "SafetyRequirement", "SafetyControl", "SafetyMechanism"}
SECURITY = {"Threat", "AttackPath", "SecurityRisk", "SecurityGoal", "SecurityRequirement", "SecurityControl", "SecurityAsset"}
HARDWARE = {"Component", "Hardware", "Controller", "ECU", "Sensor", "Actuator", "Gateway"}


def build_assurance(snapshot, domain):
    from core.eip_frontend import legacy_projections as p
    from core.safety.hara_service import build_hara_assessment
    from core.security.tara_service import build_tara_assessment
    snapshot = verification_snapshot(snapshot)
    access = permissions(snapshot["project_id"])
    assessed = assess_verification(snapshot)
    safety = domain == "safety"
    kinds, method = (SAFETY, "hara") if safety else (SECURITY, "tara")
    relevant = [item for item in snapshot["objects"] if _active(item) and (item["type"] in kinds or
        item["type"] == "Requirement" and ("safety" in p._text(item).lower() if safety else p._is_security_requirement(item)))]
    analysis, tree, details, method_rows = [], [], {}, []
    for item in relevant:
        ref, raw = item["ref"], _metadata(item)
        related = {link["targetRef"] if link["sourceRef"] == ref else link["sourceRef"]
                   for link in snapshot["links"] if ref in (link["sourceRef"], link["targetRef"]) and _active(link)}
        related_rows = [snapshot["by_ref"][value] for value in sorted(related) if value in snapshot["by_ref"]
                        and _active(snapshot["by_ref"][value])]
        def refs(*types):
            return [row["ref"] for row in related_rows if row["type"] in types]
        state = assessed["byTarget"].get(ref, {})
        evidence = state.get("currentApprovedEvidenceRefs", [])
        controls = [row for row in related_rows if row["type"] in {"SafetyControl", "SafetyMechanism", "SecurityControl"}]
        approved = currently_approved(snapshot, item)
        controlled = bool(controls) and all(currently_approved(snapshot, row) for row in controls)
        qualified = state.get("verificationQualified") is True
        status = "covered" if approved and qualified else "partial" if state.get("caseRefs") else "unknown"
        node = {"id": ref, "ref": ref, "label": item["title"], "kind": item["type"],
                "meta": "Core; unabhängiger Nachweis separat", "status": status, "children": []}
        from core.frameworks.postgres_lifecycle import allowed_lifecycle_actions
        actions = allowed_lifecycle_actions({**item, "object_type": item["type"],
            "technical_metadata": raw, "lifecycle_status": item.get("lifecycle_status", item.get("lifecycleStatus"))})
        for action in actions:
            if not access["can_edit"]:
                action["allowed"] = False
                action["reasons"] = [*action["reasons"], "Project edit permission required."]
        node.update(revision=item.get("revision"), actualLifecycle=item.get("lifecycle_status", item.get("lifecycleStatus")),
                    allowedLifecycleActions=actions)
        row = {"id": ref, "ref": ref, "label": item["title"], "kind": item["type"], "revision": item.get("revision"),
               "functions": refs("Function", "SubFunction"), "hardware": refs(*HARDWARE),
               "testCases": state.get("caseRefs", []), "evidence": len(evidence), "evidenceRefs": evidence,
               "status": status, "sourceKind": "core", "independentlyApproved": approved,
               "verificationQualified": qualified, "qualificationGaps": state.get("qualificationGaps", [])}
        if safety:
            row["asil"] = raw.get("asil")
        else:
            row.update({"severity": raw.get("severity") if raw.get("severity") in {"info", "warning", "critical"} else "info",
                        "likelihood": raw.get("likelihood"), "mitigated": bool(approved and qualified and controlled)})
        tree.append(node)
        analysis.append(row)
        details[ref] = {"node": node, "description": raw.get("description") or "",
            "properties": [{"label": "Core-Revision", "value": str(item.get("revision") or "Unbekannt")},
                           {"label": "Freigabe", "value": "aktuell unabhängig geprüft" if approved else "unbestätigt"}],
            "functions": _mappings(snapshot, row["functions"]), "hardware": _mappings(snapshot, row["hardware"]),
            "communication": _mappings(snapshot, refs("Signal", "Message", "Interface", "Port")),
            "testCases": _mappings(snapshot, row["testCases"]), "evidence": _evidence(snapshot, evidence, assessed),
            "reviews": [], "digitalThread": _mappings(snapshot, list(related))}
        # One actual source per call prevents index-based IDs/broad fallback
        # selection from becoming cross-object evidence or normative risk facts.
        source = {**raw, "id": ref, "title": item["title"], "status": "draft"}
        context = {"requirements": [source], "industry": snapshot.get("manifest", {}).get("industry"),
                   "reviews": [], "test_cases": [], "trace_links": [], "controls": [], "evidence_count": 0}
        if item["type"] in {"Hazard", "SafetyRisk"}:
            context["hazards" if item["type"] == "Hazard" else "risks"] = [source]
        if item["type"] in {"Threat", "SecurityRisk"}:
            context["threats" if item["type"] == "Threat" else "risks"] = [source]
        candidate = (build_hara_assessment if safety else build_tara_assessment)(context)
        values = dict(next(iter(candidate["items"]), {}))
        values.update({"id": f"{method}-candidate:{ref}", "evidence_status": "separately_verified",
                       "review_status": "candidate_review_required", "source": "assistive_candidate"})
        method_rows.append({"id": f"{method}-candidate:{ref}", "ref": ref, "method": method,
            "sourceRevision": item.get("revision"), "candidate": True, "reviewRequired": True,
            "riskModel": candidate["risk_model"], "candidateValues": values,
            "evidenceRefs": evidence, "currentApprovedEvidenceCount": len(evidence),
            "reviewStatus": "approved-source" if approved else "unverified-source",
            "gaps": sorted(set(state.get("gaps", ["current_approved_evidence_missing"]) +
                               [gap["code"] for gap in state.get("qualificationGaps", [])])),
            "limitations": "Heuristische Risikokandidaten mit Standardannahmen; keine normative Bewertung oder Releasefreigabe."})
    gaps = ["Keine fachlich zugeordneten Core-Objekte."] if not relevant else []
    gaps += [f"{row['ref']}: aktueller unabhängiger Nachweis fehlt." for row in analysis if row["status"] != "covered"]
    unsupported = ("fmea", "fta", "nis-evidence", "stpa", "hazop", "bowtie") if safety else ("attack-tree", "stride", "nis-security-evidence")
    from core.assurance_methods import METHODS, SCHEMA
    drafts = []
    for item in snapshot["objects"]:
        raw = _metadata(item)
        if item["type"] != "AssuranceAnalysis" or not _active(item) or raw.get("schemaVersion") != SCHEMA or raw.get("domain") != domain:
            continue
        sources = raw.get("sourceRevisions", {})
        stale = [ref for ref, revision in sources.items() if ref not in snapshot["by_ref"] or
            not _active(snapshot["by_ref"][ref]) or snapshot["by_ref"][ref].get("revision") != revision]
        drafts.append({"ref": item["ref"], "title": item["title"], "revision": item["revision"],
            "method": raw["method"], "sourceRevisions": sources, "analysis": raw["analysis"],
            "assessment": raw["assessment"], "freshness": "OUTDATED" if stale else "CURRENT", "staleSources": stale})
    return {"project": snapshot["header"], "systemContext": p._system_context(snapshot),
        "scopeLabel": f"Typed Core {domain.title()}", "tree": tree, "analysis": analysis,
        "details": details, "traceWindow": None, "methodRows": method_rows,
        "draftAnalyses": drafts[:50], "draftAnalysisTotal": len(drafts), "canEditAnalyses": access["can_edit"],
        "capabilities": [{"id": method, "label": method.upper(), "available": True,
            "reason": "Assistive, quellgebundene Kandidaten; fachliche Freigabe separat."},
            *({"id": key, "label": key.upper(), "available": key in METHODS,
               "reason": "Quellengebundener Draft; separate Prüfung erforderlich." if key in METHODS else "Kein validierter Methoden-Service angeschlossen."} for key in unsupported)],
        "assessmentPolicy": {"status": "candidate", "ruleId": "eip.assurance-projection.v1",
            "truthBoundary": "Verknüpfung ist keine Risikominderung; Kandidat ist keine Freigabe.",
            "core_writes_performed": False, "releaseApproved": False},
        "assessmentVersion": assessed["assessmentVersion"],
        "validation": {"isValid": not gaps, "errors": [], "warnings": gaps}}
