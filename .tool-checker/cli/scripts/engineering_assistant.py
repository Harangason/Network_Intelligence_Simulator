"""Evidence-backed Engineering Assistant gate, called by Checker.finish."""
STATUSES = {"COMPLETED", "WAITING_FOR_ENGINEERING_DECISION",
            "BLOCKED_WITH_EXPLICIT_CAUSE", "NOT_SUPPORTED_WITH_CAPABILITY_GAP"}
COMMON = ["goal_understood","model_inspected","context_correct","goal_typed",
          "skills_tools_selected","completion_correct"]
MUTATION = ["core_effect","dependencies_updated","routing_valid","capacity_checked",
            "timing_checked","validation_executed","preflight_checked","persistence_verified"]

def validate_contract(c):
    if not isinstance(c,dict) or c.get("expected_status") not in STATUSES:
        raise ValueError("Explicit Assistant expected_status required")
    if type(c.get("mutation_expected")) is not bool:
        raise ValueError("Explicit Assistant mutation_expected required")
    if not isinstance(c.get("checks"),list) or not all(isinstance(x,str) and x for x in c["checks"]):
        raise ValueError("Assistant checks required")
    if not isinstance(c.get("expected_values",{}),dict):
        raise ValueError("Assistant expected_values must be an object")

def evaluate(contract, actual, evidenced, kinds):
    validate_contract(contract)
    failures, missing = [], []
    if not isinstance(actual,dict):
        return {"failures": [], "missing": ["ASSISTANT_EVIDENCE_MISSING"]}
    if actual.get("generic_error") is True and evidenced(actual):
        failures.append("ASSISTANT_GENERIC_ERROR_ON_VALID_COMMAND")
    if actual.get("status") not in STATUSES:
        failures.append("ASSISTANT_INVALID_END_STATE")
    elif actual["status"] != contract["expected_status"]:
        failures.append("ASSISTANT_UNEXPECTED_END_STATE")
    if not evidenced(actual):
        missing.append("ASSISTANT_COMPLETION_EVIDENCE_MISSING")
    required = COMMON + contract["checks"]
    if contract["mutation_expected"]:
        required += MUTATION
        missing += ["ASSISTANT_"+k.upper()+"_EVIDENCE_MISSING" for k in ("model","validation")
                    if k not in kinds]
    missing += ["ASSISTANT_"+k.upper()+"_EVIDENCE_MISSING" for k in ("browser","backend","screenshot")
                if k not in kinds]
    if actual.get("status") in ("BLOCKED_WITH_EXPLICIT_CAUSE","NOT_SUPPORTED_WITH_CAPABILITY_GAP"):
        if not actual.get("cause"):
            missing.append("ASSISTANT_EXPLICIT_CAUSE_MISSING")
    if actual.get("status") == "WAITING_FOR_ENGINEERING_DECISION" and not actual.get("question"):
        missing.append("ASSISTANT_ENGINEERING_QUESTION_MISSING")
    checks=actual.get("checks",[])
    if not isinstance(checks,list):
        checks=[]
    for name in dict.fromkeys(required+list(contract.get("expected_values",{}))):
        entries=[x for x in checks if isinstance(x,dict) and x.get("name")==name and evidenced(x)]
        expected=contract.get("expected_values",{}).get(name,True)
        def matches(value):
            return type(value) is type(expected) and value==expected
        if any(not matches(x.get("value")) for x in entries):
            failures.append("ASSISTANT_CHECK_FAILED:"+name)
        elif not entries:
            missing.append("ASSISTANT_CHECK_MISSING:"+name)
    if actual.get("generic_error") is not False and "ASSISTANT_GENERIC_ERROR_ON_VALID_COMMAND" not in failures:
        missing.append("ASSISTANT_GENERIC_ERROR_UNASSESSED")
    return {"failures":failures,"missing":missing}
