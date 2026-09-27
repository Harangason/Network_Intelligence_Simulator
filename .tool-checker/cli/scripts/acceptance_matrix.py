"""Generate coverage candidates from reviewed registry exports; no test execution."""
import argparse, hashlib, json
from pathlib import Path
from tool_check import read, write, digest
DIMENSIONS=("context_state","input_quality","followup","expected_effect")
REGISTRIES=("capability_registry","domain_registry","goal_registry","technology_registry")

def generate(data):
    if any(not isinstance(data.get(k),list) or not data[k] for k in REGISTRIES):
        raise ValueError("Four nonempty registry exports required")
    domains={x["id"] for x in data["domain_registry"]}
    goals={x["id"] for x in data["goal_registry"]}
    cases=[];gaps=[];seen=set()
    for cap in data["capability_registry"]:
        if cap["id"] in seen: raise ValueError("Duplicate capability")
        seen.add(cap["id"])
        if cap["domain"] not in domains or cap["goal"] not in goals: raise ValueError("Unregistered domain/goal")
        scenarios=cap.get("scenarios",[])
        for polarity in ("positive","negative"):
            if not any(x.get("polarity")==polarity for x in scenarios):gaps.append({"capability":cap["id"],"missing":polarity})
        for i,case in enumerate(scenarios):
            if case.get("intent") not in cap["intents"]: raise ValueError("Unregistered intent")
            if case.get("polarity") not in ("positive","negative"):raise ValueError("Explicit polarity required")
            if any(not isinstance(case.get(k),str) or not case[k] for k in DIMENSIONS):raise ValueError("All matrix dimensions required")
            prompts=case.get("prompts",[])
            if not prompts: gaps.append({"capability":cap["id"],"missing":"prompts"})
            for n,prompt in enumerate(prompts):
                if not isinstance(prompt,str) or not prompt.strip():raise ValueError("Invalid prompt")
                stable=digest([cap["id"],case,n])[:20]
                cases.append({**case,"case_id":"FS-"+stable,"capability":cap["id"],"domain":cap["domain"],
                              "goal":cap["goal"],"prompt":prompt,"status":"UNMAPPED"})
        for intent in cap["intents"]:
            if not any(x.get("intent")==intent for x in scenarios):gaps.append({"capability":cap["id"],"missing":"intent:"+intent})
    if not cases:gaps.append({"missing":"executable candidates"})
    return {"registry_hash":digest(data),"cases":cases,"gaps":gaps,
            "capabilities":sorted(seen),"note":"Map every candidate to a reviewed existing Checker contract; no execution claimed."}

def coverage(matrix, results):
    ids=[c["case_id"] for c in matrix["cases"]]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate case IDs")
    if set(results)-set(ids):raise ValueError("Unexpected results")
    groups={};missing=[];failed=[]
    for case in matrix["cases"]:
        result=results.get(case["case_id"],{})
        # References to real checker runs are mandatory; raw booleans are not results.
        ok=result.get("status")=="PASSED" and bool(result.get("run_id")) and bool(result.get("evidence_refs"))
        if not ok: (missing if not result else failed).append(case["case_id"])
        key=case["domain"]+" × "+case["intent"]
        cell=groups.setdefault(key,{"required":0,"passed":0});cell["required"]+=1;cell["passed"]+=int(ok)
    return {"gate":"PASSED" if ids and not matrix["gaps"] and not missing and not failed else "FAILED",
            "domain_intent":groups,"unexecuted":missing,"failed_or_unverified":failed,"registry_gaps":matrix["gaps"],
            "scope":"Coverage accounting only; validate actual run evidence and campaign gate separately."}

def main():
    p=argparse.ArgumentParser();p.add_argument("action",choices=["generate","coverage"])
    p.add_argument("--input",required=True);p.add_argument("--results");p.add_argument("--output",required=True)
    a=p.parse_args();data=read(a.input)
    write(a.output,generate(data) if a.action=="generate" else coverage(data,read(a.results)))
if __name__=="__main__":main()
