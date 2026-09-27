"""Exact, evidence-backed call assertions: context reads are not agent executions."""
from tool_check import ident

FIELDS = {"operation", "target", "outcome", "phase", "error_code"}
REQUIRED = {"operation", "target", "outcome"}
OUTCOMES = {"EXECUTED", "REJECTED", "FAILED"}

def validate_assertions(assertions):
    if not isinstance(assertions, list):
        raise ValueError("call_assertions must be a list")
    ids = []
    for assertion in assertions:
        if not isinstance(assertion, dict):
            raise ValueError("Invalid call assertion")
        ids.append(ident(assertion.get("id")))
        selector = assertion.get("match")
        if not isinstance(selector,dict) or not REQUIRED <= selector.keys() or not selector.keys() <= FIELDS:
            raise ValueError("Call assertions require exact operation, target and outcome selectors")
        if any(not isinstance(value,str) or not value or "*" in value for value in selector.values()):
            raise ValueError("Call selectors must be nonempty exact strings, not wildcards")
        if selector["outcome"] not in OUTCOMES:
            raise ValueError("Call outcome must be EXECUTED, REJECTED or FAILED")
        lower, upper = assertion.get("min",0), assertion.get("max")
        if type(lower) is not int or lower < 0 or (upper is not None and (type(upper) is not int or upper < lower)):
            raise ValueError("Invalid call count limits")
        if "min" not in assertion and "max" not in assertion:
            raise ValueError("Explicit call count constraint required")
    if len(ids)!=len(set(ids)):
        raise ValueError("Duplicate call assertion IDs")

def evaluate_assertions(assertions, trace, evidenced):
    validate_assertions(assertions)
    result = {"failures":[], "missing":[], "assertions":[]}
    if not isinstance(trace,dict) or trace.get("complete") is not True or not evidenced(trace):
        result["missing"].append("TC_CALL_TRACE_INCOMPLETE")
        return result
    calls=trace.get("calls")
    if not isinstance(calls,list):
        result["missing"].append("TC_CALL_TRACE_INVALID")
        return result
    # Never turn malformed, omitted or unobserved calls into proof of absence.
    for call in calls:
        if (not isinstance(call,dict) or not REQUIRED <= call.keys()
            or any(not isinstance(call[k],str) or not call[k] for k in REQUIRED)
            or call["outcome"] not in OUTCOMES or not evidenced(call)):
            result["missing"].append("TC_CALL_TRACE_INVALID")
            return result
    for assertion in assertions:
        matches=[i for i,call in enumerate(calls)
                 if all(call.get(k)==v for k,v in assertion["match"].items())]
        count=len(matches)
        passed=count>=assertion.get("min",0) and (assertion.get("max") is None or count<=assertion["max"])
        result["assertions"].append({"id":assertion["id"],"match":assertion["match"],
                                    "matched_indices":matches,"actual_count":count,"status":"PASSED" if passed else "FAILED"})
        if not passed: result["failures"].append("TC_CALL_CONTRACT_VIOLATION:"+assertion["id"])
    return result
