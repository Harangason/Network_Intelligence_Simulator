"""Attach real scoped evidence without claiming a pending release passed."""
from pathlib import Path
import json
from record_evidence import reference, record

HERE = Path(__file__).resolve().parent

for scope in ("nis", "eip"):
    record(scope)
    path = HERE / f"{scope}-workload.json"
    work = json.loads(path.read_text())
    review = reference(HERE / "implementation-review.json")
    patch = reference(HERE / f"{scope}-owned.diff")
    for outcome in work["required_outcomes"]:
        if outcome != "verified_delivery":
            work["outcomes"][outcome] = {"status": "PASSED", "scope": "Implemented capability; no normative conformity or independent human approval asserted", "evidence": [review, patch]}
    log_names = {"targeted_unit": "nis-isolated-final.log" if scope == "nis" else "eip-unit.log", "isolated_sql": "import-provenance-isolated.log" if scope == "nis" else "eip-isolated.log", "frontend_typecheck": f"{scope}-typecheck.log"}
    for name, log in log_names.items():
        work["validations"][name] = {"status": "PASSED", "evidence": [reference(HERE / log), review]}
    work["validations"]["release_gate"] = {"status": "BLOCKED" if scope == "nis" else "NOT_RUN", "reason": "Strict gate rejected candidate Git revision after external commit; successful unit/build checks retained. New candidate requires separately audited image cleanup, then full browser and HTTP E2E before deployment" if scope == "nis" else "User explicitly excludes EIP production delivery; no full campaign or product verification claimed", "evidence": [review]}
    work["outcomes"]["verified_delivery"] = {"status": "PENDING" if scope == "nis" else "NOT_DEPLOYED", "evidence": [review]}
    if scope == "eip":
        work["delivery"] = {"decision": "NO", "authorization": "Direct user reply to call_22a83d2132bb4bd48eef8ff5e404bab3: EIP vorerst nicht übernehmen", "target": "Existing local EIP instance", "scope": "Implementation retained; no product restart performed"}
        work["completion_status"] = "IMPLEMENTED_NOT_DEPLOYED_BY_USER"
    else:
        work["completion_status"] = "RELEASE_BLOCKED"
    path.write_text(json.dumps(work, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
