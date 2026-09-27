"""Evidence-backed routing of repairs; never infer ownership from symptoms."""
OWNERS={"TOOL_CHECKER","NIS_PRODUCT","SHARED","ENVIRONMENT","TEST_DATA","UNKNOWN"}
def validate(plan, executable=False):
    owner=plan.get("repair_owner")
    if owner not in OWNERS: raise ValueError("Explicit repair_owner required")
    repository=plan.get("affected_repository")
    if repository not in {"TOOL_CHECKER","NIS","BOTH"}: raise ValueError("Explicit affected_repository required")
    if owner=="TOOL_CHECKER" and repository!="TOOL_CHECKER": raise ValueError("Checker defect must target Checker")
    if owner=="NIS_PRODUCT" and repository!="NIS": raise ValueError("Product defect must target NIS")
    if owner=="SHARED":
        if repository!="BOTH": raise ValueError("Shared repair must identify both repositories")
        defects=plan.get("independent_defects",[])
        if len(defects)<2 or not all(isinstance(d,dict) and d.get("root_cause") and d.get("evidence") for d in defects):
            raise ValueError("SHARED needs two independently evidenced causes")
        if len({d["root_cause"] for d in defects})<2: raise ValueError("Duplicate causes are not SHARED")
    for name in ("observed_symptom","execution_boundary","last_successful_layer","first_failing_layer",
                 "root_cause","affected_files","affected_services","targeted_tests","routing_evidence"):
        if not plan.get(name): raise ValueError("Missing routing field: "+name)
    if plan.get("expectation_changed") and not all(plan.get(k) for k in ("rationale","source_requirement","review_evidence")):
        raise ValueError("Expectation change requires requirement and review evidence")
    if plan.get("weaken_assertions_to_pass") is not False:
        raise ValueError("Explicit no-weakening declaration required")
    if executable and (owner=="UNKNOWN" or plan.get("decision_required") is not False):
        raise ValueError("Unresolved root cause/engineering decision blocks repair")
    return plan
