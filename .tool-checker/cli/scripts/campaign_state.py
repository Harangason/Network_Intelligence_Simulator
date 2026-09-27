"""Campaign orchestration for the existing Checker; no second test executor."""
from pathlib import Path
import collections
import subprocess
import uuid
from tool_check import read, write, digest, file_hash, ident, now

MAX_RUNS = 3
TERMINAL = {"PASSED", "FAILED", "REPAIR_APPLIED_AWAITING_NEW_CAMPAIGN", "STOPPED"}
VERSION_KEYS = ("build_id", "commit_id", "skill_version", "mcp_registry_version",
                "model_schema_version", "technology_profile_version")

def require(condition, message):
    if not condition:
        raise ValueError("CAMPAIGN_POLICY_VIOLATION: " + message)

def file_ref(path):
    p = Path(path).resolve(strict=True)
    require(p.is_file() and p.stat().st_size > 0, "Nonempty evidence required")
    return {"path": str(p), "sha256": file_hash(p)}

def intact(ref):
    try:
        return file_hash(ref["path"]) == ref["sha256"]
    except (OSError, KeyError):
        return False

def project_lock(tc):
    return Path(tc.cfg()["project"])/".tool-checker/locks/campaign.json"

def attached(tc):
    path = project_lock(tc)
    if not path.exists():
        return None
    lock = read(path)
    require(lock["state"] == str(tc.root), "Campaign belongs to another state directory")
    return Campaign(tc, lock["campaign_id"])

class Campaign:
    def __init__(self, tc, campaign_id):
        self.tc = tc
        self.id = ident(campaign_id)
        self.dir = tc.root/"campaigns"/self.id
        self.path = self.dir/"campaign.json"
    def load(self):
        return read(self.path)
    def save(self, c):
        c["updated_at"] = now()
        write(self.path, c)
        return c
    def locked(self):
        lock = project_lock(self.tc)
        require(lock.exists() and read(lock) == {"state": str(self.tc.root), "campaign_id": self.id},
                "Campaign lock missing or different owner")
    def idle_executors(self):
        for p in self.tc.root.glob("tasks/*/results/*/result.json"):
            require(read(p)["status"] != "RUNNING", "A test is still running")
        for p in self.tc.root.glob("jobs/*/job.json"):
            require(read(p).get("status") not in ("QUEUED", "RUNNING", "WAITING_FOR_USER", "WAITING_FOR_DECISION"),
                    "A background job is still pending")
        require(not self.tc.lock_path().exists(), "Mutation lock held")
    def create(self, task):
        require(not self.path.exists(), "Campaign already exists")
        self.idle_executors()
        require(not self.tc.verify(task), "Source/preflight contracts need revalidation")
        cases = self.tc.select(task=task)
        require(bool(cases), "Empty suite")
        policy = read(Path(__file__).resolve().parent.parent/"config/campaign-policy.json")
        require(policy.get("max_full_runs") == MAX_RUNS and policy.get("repair_during_full_run") is False
                and policy.get("automatic_run_after_run_3") is False, "Unsupported campaign policy")
        lock = project_lock(self.tc)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open("x", encoding="utf-8") as f:
            import json
            json.dump({"state": str(self.tc.root), "campaign_id": self.id}, f)
        return self.save({"campaign_id": self.id, "task_id": task, "state": "IDLE",
                          "run_number": 0, "suite": [x["test_id"] for x in cases],
                          "policy": policy, "rounds": [], "ledger": {}, "repairs": {}, "created_at": now()})
    def snapshot(self, c, build_path):
        require(not self.tc.verify(c["task_id"]), "Source/rules invalid")
        cases = self.tc.select(task=c["task_id"])
        require(sorted(c["suite"]) == sorted(x["test_id"] for x in cases), "Full suite IDs changed")
        build = read(build_path)
        require(all(isinstance(build.get(k), str) and build[k].strip() for k in VERSION_KEYS),
                "All build/version identifiers required; use explicit not-applicable with reason")
        require(isinstance(build.get("files"), list) and bool(build["files"]), "Build files/receipt required")
        from runtime_delivery import snapshot
        runtime = snapshot(self.tc.cfg(), build)
        return {"runtime": runtime, "build": {k: build[k] for k in VERSION_KEYS},
                "files": [file_ref(p) for p in build["files"]],
                "manifest": file_ref(self.tc.task(c["task_id"])/"manifest.json"),
                "contracts": {x["test_id"]: x["contract_hash"] for x in cases}}
    def run(self, build_path):
        self.locked()
        c = self.load()
        require(c["state"] == "IDLE" or c["state"] == f"REPAIR_{c['run_number']}_COMPLETE",
                "Full run requires completed repair")
        require(c["run_number"] < MAX_RUNS, "Maximum three full runs; no automatic run 4")
        self.idle_executors()
        frozen = self.snapshot(c, build_path)
        for plan in c["repairs"].values():
            if plan["round"] == c["run_number"] and plan.get("deployment_required"):
                from runtime_delivery import verify_delivery, matches
                verify_delivery(plan, c.get("deliveries",{}).get(plan["repair_id"]))
                require(matches(plan["expected_runtime_version"], frozen["runtime"].get("observed",{}).get("fingerprint")), "Pending deployment or wrong runtime build")
        number = c["run_number"] + 1
        c["run_number"] = number
        c["state"] = f"RUN_{number}_ACTIVE"
        c["rounds"].append({"number": number, "started_at": now(), "snapshot": frozen,
                            "tests": {}, "blocked": {}, "frozen": False})
        write(self.dir/f"run-{number}"/"manifest.json", frozen)
        return self.save(c)
    def drift(self, c):
        r = c["rounds"][-1]
        refs = [r["snapshot"]["manifest"], *r["snapshot"]["files"]]
        issues = ["FROZEN_BUILD_OR_MANIFEST_CHANGED"] if not all(intact(x) for x in refs) else []
        if "runtime" in r["snapshot"]:
            from runtime_delivery import drift
            issues += drift(r["snapshot"]["runtime"])
        else:
            issues.append("RUNTIME_CONTRACT_MISSING_LEGACY_RUN")
        issues += self.tc.verify(c["task_id"])
        cases = self.tc.select(task=c["task_id"])
        if {x["test_id"]: x["contract_hash"] for x in cases} != r["snapshot"]["contracts"]:
            issues.append("FROZEN_TEST_CONTRACT_CHANGED")
        return issues
    def test_start(self, task, test):
        self.locked()
        c = self.load()
        if c["state"] in ("REPAIR_1_ACTIVE", "REPAIR_2_ACTIVE", "POST_REPAIR_ACTIVE"):
            case = self.tc.select(test, task)[0]
            require("repair-verification" in case["tags"], "Only targeted repair-verification tests in repair phase")
            return None
        require(c["state"] == f"RUN_{c['run_number']}_ACTIVE", "No active full run")
        require(task == c["task_id"] and test in c["suite"], "Case outside campaign suite")
        require(not self.drift(c), "Frozen build/manifest drift")
        r = c["rounds"][-1]
        require(test not in r["tests"] and test not in r["blocked"], "Case already attempted this round")
        return {"campaign_id": self.id, "round": c["run_number"]}
    def bind(self, test, run_id):
        c = self.load()
        c["rounds"][-1]["tests"][test] = run_id
        self.save(c)
    def block(self, test, reason, evidence):
        self.locked()
        c = self.load()
        require(c["state"] == f"RUN_{c['run_number']}_ACTIVE", "No active full run")
        r = c["rounds"][-1]
        require(test in c["suite"] and test not in r["tests"] and test not in r["blocked"], "Case already attempted or unknown")
        require(isinstance(reason, str) and bool(reason.strip()), "Explicit blocker reason required")
        r["blocked"][test] = {"status": "BLOCKED", "reason": reason, "evidence": file_ref(evidence)}
        return self.save(c)
    def close_run(self):
        self.locked()
        c = self.load()
        require(c["state"] == f"RUN_{c['run_number']}_ACTIVE", "No active full run")
        r = c["rounds"][-1]
        require(set(r["tests"]) | set(r["blocked"]) == set(c["suite"]), "All suite cases must be accounted for")
        self.idle_executors()
        drift = self.drift(c)
        results, findings = {}, []
        for test in c["suite"]:
            if test in r["blocked"]:
                result = r["blocked"][test]
                require(intact(result["evidence"]), "Blocker evidence changed")
            else:
                run_id = r["tests"][test]
                p = self.tc.run_dir(run_id, c["task_id"])/"result.json"
                result = read(p)
                require(result.get("campaign") == {"campaign_id": self.id, "round": c["run_number"]},
                        "Result from another campaign/round")
                require(result["status"] in ("PASSED", "FAILED", "BLOCKED", "PARTIAL"), "Unfinished result")
                for ev in result["evidence"]:
                    require(intact({"path": str(p.parent/ev["path"]), "sha256": ev["sha256"]}), "Evidence changed")
                result = {**result, "result_ref": file_ref(p)}
            if result["status"] == "PARTIAL":
                result = {**result, "status": "BLOCKED", "reason": "Missing required evidence/checks"}
            results[test] = result
            if result["status"] != "PASSED":
                details = result.get("findings") or [{"category": "ENVIRONMENT_ERROR" if result["status"] == "BLOCKED" else "PRODUCT_BUG",
                                                      "code": result.get("reason") or "|".join(result.get("failures", [])) or "TEST_FAILED"}]
                for item in details:
                    key = digest([item.get("category"), item.get("code"), item.get("object_refs", []), test])[:20]
                    old = c["ledger"].get(key)
                    previous = c["rounds"][-2].get("statuses", {}).get(test) if len(c["rounds"]) > 1 else None
                    record = {**item, "finding_id": key, "test_id": test, "campaign_id": self.id,
                              "classification": item.get("category", "UNKNOWN"),
                              "repair_owner": "UNKNOWN",
                              "severity": item.get("severity", "P1" if "critical" in result.get("context",{}).get("test",{}).get("tags",[]) else "P2"),
                              "object_refs": item.get("object_refs", []),
                              "evidence_refs": result.get("evidence", []),
                              "run_id": f"run-{c['run_number']}", "first_seen_run": old["first_seen_run"] if old else c["run_number"],
                              "last_seen_run": c["run_number"], "status": "OPEN",
                              "reopened": bool(old and old["status"] == "RESOLVED"),
                              "regression": previous == "PASSED",
                              "root_cause_id": item.get("root_cause_id", old.get("root_cause_id") if old else None)}
                    findings.append(record)
                    c["ledger"][key] = record
        if drift:
            findings.append({"finding_id": "campaign-drift", "category": "CAMPAIGN_POLICY_VIOLATION",
                             "code": "FROZEN_BUILD_CHANGED", "status": "OPEN", "details": drift})
            c["ledger"]["campaign-drift"] = findings[-1]
        active = {f["finding_id"] for f in findings}
        for key, old in c["ledger"].items():
            if key not in active and results.get(old.get("test_id"), {}).get("status") == "PASSED":
                old["status"] = "RESOLVED"
        for repair in c["repairs"].values():
            if repair["round"] < c["run_number"] and repair["status"] == "WAITING_FOR_NEXT_FULL_RUN":
                tests = {c["ledger"][key]["test_id"] for key in repair["finding_ids"]}
                confirmed = not drift and all(results.get(test, {}).get("status") == "PASSED" for test in tests)
                repair["status"] = "CONFIRMED_BY_FULL_RUN" if confirmed else "FAILED"
                repair["confirmed_or_failed_run"] = c["run_number"]
                if not confirmed:
                    repair["outcome"] = "REPAIR_INEFFECTIVE"
        for finding in findings:
            if finding.get("regression"):
                finding["regression_after_repairs"] = [p["repair_id"] for p in c["repairs"].values() if p["round"] == c["run_number"]-1]
                # Temporal association, not proof of causation.
        r["statuses"] = {test: result["status"] for test, result in results.items()}
        r["frozen"] = True
        r["finished_at"] = now()
        bundle = self.dir/f"run-{c['run_number']}"
        write(bundle/"results.json", results)
        write(bundle/"findings.json", findings)
        r["receipts"] = [file_ref(bundle/name) for name in ("manifest.json", "results.json", "findings.json")]
        r["gate"] = "PASSED" if not findings and all(x == "PASSED" for x in r["statuses"].values()) else "FAILED"
        r["metrics"] = dict(collections.Counter(r["statuses"].values()))
        r["metrics"].update(total=len(results), regressions=sum(bool(f.get("regression")) for f in findings),
                            reopened=sum(bool(f.get("reopened")) for f in findings),
                            new_findings=sum(f.get("first_seen_run") == c["run_number"] for f in findings))
        r["metrics"].update(
            pass_rate=100*r["metrics"].get("PASSED",0)/len(results),
            failure_rate=100*r["metrics"].get("FAILED",0)/len(results),
            blocked_rate=100*r["metrics"].get("BLOCKED",0)/len(results),
            critical_findings=sum(f.get("severity") in ("P0","P1") for f in findings),
            resolved_findings=sum(f["status"] == "RESOLVED" for f in c["ledger"].values()))
        assistant = [x.get("actual",{}).get("engineering_assistant") for x in results.values()
                     if x.get("context",{}).get("test",{}).get("engineering_assistant")]
        r["assistant"] = {"commands_tested": len(assistant),
                          "end_states": dict(collections.Counter(x.get("status","MISSING") if isinstance(x,dict) else "MISSING" for x in assistant)),
                          "generic_errors": sum(isinstance(x,dict) and x.get("generic_error") is True for x in assistant),
                          "gate_passed": all(x["status"] == "PASSED" for x in results.values()
                                            if x.get("context",{}).get("test",{}).get("engineering_assistant")) and bool(assistant)}
        c["state"] = "PASSED" if r["gate"] == "PASSED" else ("FAILED" if c["run_number"] == MAX_RUNS or drift else f"RUN_{c['run_number']}_COMPLETE")
        self.save(c)
        return c
    def check_receipts(self, c):
        require(all(intact(ref) for r in c["rounds"] for ref in r.get("receipts", [])),
                "Frozen findings/results changed")
        for r in c["rounds"]:
            if not r["frozen"]:
                continue
            results = read(self.dir/f"run-{r['number']}"/"results.json")
            for result in results.values():
                if "result_ref" in result:
                    require(intact(result["result_ref"]), "Original result changed after freeze")
                    directory = Path(result["result_ref"]["path"]).parent
                    for ev in result["evidence"]:
                        require(intact({"path":str(directory/ev["path"]),"sha256":ev["sha256"]}),
                                "Original evidence changed after freeze")
                else:
                    require(intact(result["evidence"]), "Blocker evidence changed after freeze")
    def repair(self, post_run3=False):
        self.locked()
        c = self.load()
        self.check_receipts(c)
        self.idle_executors()
        if post_run3:
            require(c["state"] == "FAILED" and c["run_number"] == 3, "Post-run-3 repair requires failed final run")
            c["state"] = "POST_REPAIR_ACTIVE"
        else:
            require(c["run_number"] in (1, 2) and c["state"] == f"RUN_{c['run_number']}_COMPLETE",
                    "Repair forbidden before full run is complete")
            c["state"] = f"REPAIR_{c['run_number']}_ACTIVE"
        return self.save(c)
    def repair_guard(self):
        self.locked()
        c = self.load()
        self.check_receipts(c)
        require(c["state"] in ("REPAIR_1_ACTIVE", "REPAIR_2_ACTIVE", "POST_REPAIR_ACTIVE"),
                "Repair mutation denied")
        return c
    def plan_repair(self, plan_path):
        c = self.repair_guard()
        plan = read(plan_path)
        from repair_routing import validate
        validate(plan)
        ident(plan["repair_id"])
        require(plan.get("finding_ids") and all(x in c["ledger"] for x in plan["finding_ids"]), "Unknown findings")
        require(all(plan.get(k) for k in ("required_fix", "acceptance_criteria", "regression_scope")), "Incomplete repair plan")
        plan["routing_refs"] = [file_ref(p) for p in plan["routing_evidence"]]
        for defect in plan.get("independent_defects", []):
            plan["routing_refs"].extend(file_ref(p) for p in defect["evidence"])
        if plan.get("expectation_changed"):
            plan["review_refs"] = [file_ref(p) for p in plan["review_evidence"]]
        plan["round"] = c["run_number"]
        if plan.get("verification_passed"):
            plan["local_test_refs"] = [file_ref(p) for p in plan.get("evidence",[])]
        plan["status"] = "PLANNED"
        c.setdefault("repair_plans", {})[plan["repair_id"]] = plan
        for key in plan["finding_ids"]:
            c["ledger"][key]["repair_owner"] = plan["repair_owner"]
        return self.save(c)
    def execute_repair(self, command_path):
        c = self.repair_guard()
        command = read(command_path)
        plan = c.get("repair_plans", {}).get(command.get("repair_id"))
        require(plan and plan["round"] == c["run_number"], "Current routed repair-plan required")
        from repair_routing import validate
        validate(plan, executable=True)
        require(all(intact(p) for p in plan["routing_refs"]+plan.get("review_refs",[])), "Routing evidence changed")
        argv = command.get("argv")
        require(isinstance(argv, list) and bool(argv) and all(isinstance(x, str) and x for x in argv),
                "Explicit argv required")
        log = self.dir/f"repair-{c['run_number']}"/("execution-" + uuid.uuid4().hex + ".log")
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("wb") as out:
            result = subprocess.run(argv, cwd=self.tc.cfg()["project"], stdout=out, stderr=subprocess.STDOUT,
                                    shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"returncode": result.returncode, "evidence": file_ref(log) if log.stat().st_size else {"path": str(log)}}
    def deliver_repair(self, repair_id):
        c = self.repair_guard()
        self.idle_executors()
        plan = c.get("repair_plans",{}).get(repair_id)
        require(plan and plan["round"] == c["run_number"], "Current repair plan required")
        from repair_routing import validate
        validate(plan, executable=True)
        require(all(intact(x) for x in plan["routing_refs"]+plan.get("review_refs",[])), "Routing evidence changed")
        from runtime_delivery import execute
        receipt = execute(self.tc.cfg(),plan,self.dir/f"repair-{c['run_number']}"/repair_id)
        c.setdefault("deliveries",{})[repair_id] = receipt
        self.save(c)
        return receipt
    def record_repair(self, plan_path):
        c = self.repair_guard()
        plan = read(plan_path)
        ident(plan["repair_id"])
        from repair_routing import validate
        validate(plan, executable=True)
        require(plan.get("status") in ("TARGET_VERIFIED", "WAITING_FOR_NEXT_FULL_RUN"), "Targeted verification is not full-run confirmation")
        plan["status"] = "WAITING_FOR_NEXT_FULL_RUN"
        plan["routing_refs"] = [file_ref(p) for p in plan["routing_evidence"]]
        for defect in plan.get("independent_defects", []):
            plan["routing_refs"].extend(file_ref(p) for p in defect["evidence"])
        if plan.get("expectation_changed"):
            plan["review_refs"] = [file_ref(p) for p in plan["review_evidence"]]
        require(bool(plan.get("finding_ids")) and all(x in c["ledger"] for x in plan["finding_ids"]), "Unknown findings")
        require(all(plan.get(k) for k in ("root_cause", "affected_files", "affected_tests",
                                         "required_fix", "acceptance_criteria", "regression_scope")), "Incomplete repair plan")
        require(plan.get("verification_passed") is True and plan.get("evidence"), "Targeted verification required")
        plan["evidence_refs"] = [file_ref(p) for p in plan["evidence"]]
        from runtime_delivery import verify_delivery
        verify_delivery(plan, c.get("deliveries",{}).get(plan["repair_id"]))
        plan["delivery_status"] = "CONFIRMED_BY_RUNTIME" if plan["deployment_required"] else "NOT_APPLICABLE"
        plan["round"] = c["run_number"]
        c["repairs"][plan["repair_id"]] = plan
        for key in plan["finding_ids"]:
            c["ledger"][key]["repair_owner"] = plan["repair_owner"]
            c["ledger"][key]["root_cause_id"] = plan.get("root_cause_id", plan["repair_id"])
        return self.save(c)
    def complete_repair(self):
        c = self.repair_guard()
        self.idle_executors()
        covered = set()
        for plan in c["repairs"].values():
            if plan["round"] == c["run_number"]:
                require(plan["status"] == "WAITING_FOR_NEXT_FULL_RUN" and all(intact(x) for x in plan["evidence_refs"]+plan.get("routing_refs",[])+plan.get("review_refs",[])), "Repair evidence/status changed")
                from runtime_delivery import verify_delivery
                verify_delivery(plan, c.get("deliveries",{}).get(plan["repair_id"]))
                covered.update(plan["finding_ids"])
        require({key for key, f in c["ledger"].items() if f["status"] == "OPEN"}.issubset(covered),
                "Open/unverified repairs remain")
        c["state"] = "REPAIR_APPLIED_AWAITING_NEW_CAMPAIGN" if c["run_number"] == 3 else f"REPAIR_{c['run_number']}_COMPLETE"
        return self.save(c)
    def stop(self):
        self.locked()
        self.idle_executors()
        c = self.load()
        if c["state"] not in TERMINAL:
            c["state"] = "STOPPED"
        self.save(c)
        project_lock(self.tc).unlink()
        return c
    def report(self):
        c = self.load()
        self.check_receipts(c)
        progress = 0
        if c["rounds"]:
            r = c["rounds"][-1]
            finished = len(r["blocked"])
            for run_id in r["tests"].values():
                if read(self.tc.run_dir(run_id,c["task_id"])/"result.json")["status"] != "RUNNING":
                    finished += 1
            progress = 100 if r["frozen"] else min(99, int(100*finished/len(c["suite"])))
        return {"campaign_id": self.id, "state": c["state"], "full_runs": c["run_number"],
                "run_percentage": progress, "campaign_passed": c["state"] == "PASSED",
                "max_full_runs": MAX_RUNS, "rounds": c["rounds"], "findings": c["ledger"],
                "root_cause_clusters": {root: [key for key,f in c["ledger"].items() if f.get("root_cause_id")==root]
                                        for root in {f.get("root_cause_id") for f in c["ledger"].values()} if root},
                "deliveries": c.get("deliveries",{}), "repairs": c["repairs"], "repair_plans": c.get("repair_plans", {}), "path": str(self.path)}
