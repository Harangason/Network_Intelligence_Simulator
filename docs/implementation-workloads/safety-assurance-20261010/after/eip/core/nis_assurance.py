"""Conservative import adapter for frozen NIS evidence, not a safety calculator."""
from copy import deepcopy
from hashlib import sha256
import json
from math import isfinite

SCHEMA = "nis.safety-evidence.v1"


def evidence_hash(value):
    def canonical(item):
        if isinstance(item, dict): return {key: canonical(child) for key, child in item.items()}
        if isinstance(item, list): return [canonical(child) for child in item]
        if type(item) is float and isfinite(item) and item.is_integer(): return int(item)
        return item
    return sha256(json.dumps(canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def evaluate_nis(analysis, sources):
    if not isinstance(analysis, dict) or set(analysis) != {"nisProjectId", "eipProjectId", "bundle"}:
        raise ValueError("Explicit NIS/EIP project mapping and original evidence bundle required")
    if any(not isinstance(analysis[key], str) or not analysis[key].strip() or len(analysis[key]) > 200 for key in ("nisProjectId", "eipProjectId")):
        raise ValueError("Explicit bounded project identities required")
    bundle = analysis["bundle"]
    if not isinstance(bundle, dict) or set(bundle) != {"payload", "sha256"}:
        raise ValueError("Original payload and sha256 required")
    payload = bundle["payload"]
    digest = evidence_hash(payload)
    if digest != bundle["sha256"]:
        raise ValueError("NIS evidence content hash does not match")
    if not isinstance(payload, dict) or set(payload) != {"schema", "rule_version", "project_id", "snapshot_id", "job_id", "source_versions", "requirement_revisions", "execution_status", "freshness", "assessment", "release_approved"}:
        raise ValueError("Unsupported NIS evidence envelope")
    if payload["schema"] != SCHEMA or payload["rule_version"] != "1.0" or payload["release_approved"] is not False:
        raise ValueError("Unsupported NIS evidence version or forged release approval")
    if payload["project_id"] != analysis["nisProjectId"]:
        raise ValueError("NIS project identity mismatch")
    if payload["freshness"] not in ("CURRENT", "OUTDATED"):
        raise ValueError("Explicit provider freshness required")
    if payload["execution_status"] != "COMPLETED" or not payload["snapshot_id"] or not payload["job_id"]:
        raise ValueError("Completed original simulation snapshot and job required")
    assessment = payload["assessment"]
    if not isinstance(assessment, dict) or assessment.get("schema") != SCHEMA or assessment.get("release_approved") is not False or assessment.get("normative_status") != "NOT_EVALUATED":
        raise ValueError("Import cannot declare normative conformity or release approval")
    rows = assessment.get("requirements")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
        raise ValueError("1–64 explicitly mapped requirements required")
    used, vector, mapped = {}, {}, []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in vector or type(row.get("revision")) is not int or row["revision"] < 1:
            raise ValueError("Unique original requirement identity and positive revision required")
        if row.get("technical_status") not in ("PASS", "FAIL", "NOT_EVALUATED") or row.get("normative_status") != "NOT_EVALUATED" or row.get("review_status") != "REVIEW_REQUIRED":
            raise ValueError("Unsupported requirement assessment or forged approval")
        vector[row["id"]] = row["revision"]
        config = row.get("configuration")
        if not isinstance(config, dict) or not isinstance(config.get("profile"), dict):
            raise ValueError("Original typed requirement profile required")
        profile = config["profile"]
        for key in ("standard", "edition", "domain", "applicability", "reason"):
            if not isinstance(profile.get(key), str) or not profile[key].strip() or len(profile[key]) > 500:
                raise ValueError("Explicit bounded normative profile fields required")
        checks, refs = row.get("checks"), row.get("evidence_event_ids")
        if not isinstance(checks, list) or len(checks) > 64 or any(not isinstance(check, dict) or check.get("status") not in ("PASS", "FAIL", "NOT_EVALUATED") for check in checks):
            raise ValueError("Bounded original technical check list required")
        if not isinstance(refs, list) or len(refs) > 100000 or any(not isinstance(ref, str) or len(ref) > 500 for ref in refs):
            raise ValueError("Bounded original event references required")
        mapping = config.get("eip")
        if not isinstance(mapping, dict) or mapping.get("project_id") != analysis["eipProjectId"]:
            raise ValueError("Every requirement needs its explicit target EIP project")
        revisions = mapping.get("source_revisions")
        if not isinstance(revisions, dict) or mapping.get("requirement_ref") not in revisions or not 1 <= len(revisions) <= 20:
            raise ValueError("Original EIP requirement/source revisions required")
        for ref, revision in revisions.items():
            if ref not in sources or sources[ref] != revision or type(revision) is not int or revision < 1:
                raise ValueError("Original EIP revision mismatch")
            if ref in used and used[ref] != revision: raise ValueError("Conflicting source revisions")
            used[ref] = revision
        mapped.append({"nisRequirementId": row["id"], "nisRevision": row["revision"], "sourceRef": mapping["requirement_ref"],
            "name": row.get("name"), "profile": deepcopy((row.get("configuration") or {}).get("profile")),
            "providerTechnicalStatus": row["technical_status"], "checks": deepcopy(row.get("checks", [])),
            "eventRefs": deepcopy(row.get("evidence_event_ids", []))})
    if used != sources or vector != payload["requirement_revisions"]:
        raise ValueError("Evidence and source revision maps must match the actual cited requirements")
    if not isinstance(payload["source_versions"], dict) or not payload["source_versions"]:
        raise ValueError("Original NIS model revision vector required")
    return {"result": {"nisProjectId": analysis["nisProjectId"], "eipProjectId": analysis["eipProjectId"],
        "snapshotId": payload["snapshot_id"], "jobId": payload["job_id"], "contentHash": digest,
        "providerFreshness": payload["freshness"], "sourceAuthenticity": "UNVERIFIED_OPERATOR_IMPORT",
        "liveNisFreshness": "UNVERIFIED", "normativeStatus": "NOT_EVALUATED", "requirements": mapped},
        "gaps": ["nis_origin_requires_independent_verification", "nis_live_revision_requires_verification", "normative_lifecycle_and_regulatory_evidence_not_evaluated", "independent_review_required"]
            + (["provider_evidence_outdated"] if payload["freshness"] != "CURRENT" else [])}
