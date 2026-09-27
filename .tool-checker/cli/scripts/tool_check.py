#!/usr/bin/env python3
"""Evidence-backed local test state; source documents are never executed."""
from __future__ import annotations
import argparse
import collections
import contextlib
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone

VERSION = "1.2.0"
LISTS = """preconditions required_model_context expected_questions forbidden_questions
required_actions required_tools required_views expected_model_changes expected_calculations
expected_validations expected_visualizations completion_criteria failure_conditions required_skills tags""".split()
CHECKS = "expected_model_changes expected_calculations expected_validations expected_visualizations completion_criteria".split()
CATEGORIES = set("PRODUCT_BUG AGENT_BUG TOOL_BUG TEST_DATA_ERROR ENVIRONMENT_ERROR PERMISSION_ERROR TIMEOUT EXPECTATION_MISMATCH UNKNOWN CAMPAIGN_POLICY_VIOLATION".split())
def now(): return datetime.now(timezone.utc).isoformat()
def digest(obj): return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def read(path):
    # Windows may briefly deny opening a file while another thread atomically replaces it.
    for attempt in range(4):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8-sig"))
        except PermissionError:
            if os.name != "nt" or attempt == 3:
                raise
            time.sleep(0.02 * (2 ** attempt))
def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""): h.update(block)
    return h.hexdigest()
def write(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".tc-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False); f.write("\n"); f.flush(); os.fsync(f.fileno())
        for attempt in range(4):
            try:
                os.replace(temp, path)
                break
            except PermissionError:
                if os.name != "nt" or attempt == 3:
                    raise
                time.sleep(0.02 * (2 ** attempt))
    finally:
        if os.path.exists(temp): os.unlink(temp)
def ident(s):
    if not isinstance(s, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", s):
        raise ValueError("Invalid identifier")
    if s.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}:
        raise ValueError("Reserved identifier")
    return s
def strings(value, label):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError(label + ": array of nonempty strings required")
    if len(value) != len(set(value)): raise ValueError(label + ": duplicate entries")
    return value
def normalize(value, lines):
    c = dict(value); ident(c.get("test_id"))
    for k in ("title", "input"):
        if not isinstance(c.get(k), str) or not c[k].strip(): raise ValueError("Missing " + k)
    for k in LISTS: c[k] = strings(c.get(k, []), k)
    if not c["completion_criteria"]: raise ValueError("Completion criteria required")
    for k in ("difficulty", "variant", "architecture_variant"):
        c.setdefault(k, "")
        if not isinstance(c[k], str): raise ValueError(k + ": string required")
    for k in ("mutating", "browser_required"):
        if type(c.get(k)) is not bool: raise ValueError(k + ": explicit boolean required")
    span = c.get("source_lines")
    if not isinstance(span, list) or len(span) != 2 or any(type(x) is not int for x in span) or not 1 <= span[0] <= span[1] <= lines:
        raise ValueError("source_lines must be a valid inclusive line range")
    c.setdefault("decision_mode", "INTERACTIVE")
    if c["decision_mode"] not in ("INTERACTIVE", "SCRIPTED"): raise ValueError("Invalid decision mode")
    if c["decision_mode"] == "SCRIPTED" and not c.get("expected_decision"): raise ValueError("Expected decision required")
    c.setdefault("overall_timeout", 1800)
    if type(c["overall_timeout"]) is not int or c["overall_timeout"] < 1: raise ValueError("Invalid timeout")
    if "call_assertions" in c:
        from call_contract import validate_assertions
        validate_assertions(c["call_assertions"])
    if "engineering_assistant" in c:
        from engineering_assistant import validate_contract
        validate_contract(c["engineering_assistant"])
    c["contract_hash"] = digest({k:v for k,v in c.items() if k not in ("status", "last_run", "contract_hash")})
    c.update(status="READY", last_run=None)
    return c

class RulesManagerAdapter:
    """Preserves unrelated text in an existing Markdown rules registry."""
    def __init__(self, path): self.path = Path(path)
    def markers(self, task): return f"<!-- tool-check:{ident(task)} -->", f"<!-- /tool-check:{ident(task)} -->"
    def find_rule(self, task):
        if not self.path.exists(): return None
        body = self.path.read_text(encoding="utf-8-sig"); begin, end = self.markers(task)
        if begin not in body: return None
        if body.count(begin) != 1 or body.count(end) != 1 or body.index(end) < body.index(begin):
            raise ValueError("Malformed registry markers")
        return body[body.index(begin):body.index(end)+len(end)]
    def register_rule(self, m, status="ACTIVE"):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        begin, end = self.markers(m["task_id"]); previous = self.find_rule(m["task_id"])
        body = self.path.read_text(encoding="utf-8-sig") if self.path.exists() else "# Aufgabenbezogenes Regelregister\n"
        block = "\n".join([begin, "## Tool Check: " + m["task_id"], "",
            "- Category: Tool Check", "- Skill: tool-checker", "- Source: " + m["source"],
            "- Source Hash: " + m["source_hash"], "- Status: " + status,
            "- Last Ingest: " + m["updated_at"], "- Manifest: " + m["manifest_path"], "",
            "Use the normalized manifest after source/rule hash checks. Re-analyze changed sources.",
            "Perform UI checks with the available browser skill and actual browser tools.",
            "PASS requires stored evidence and verified completion criteria.",
            "Default presentation: PROGRESS. Percentage, status and step counters come from runtime events.",
            "Progress rendering never invokes an LLM. Full local logs are shown only on request.",
            "This task registration does not replace project contracts or confer new permissions.", end])
        updated = body.replace(previous, block) if previous else body.rstrip() + "\n\n" + block + "\n"
        self.path.write_text(updated, encoding="utf-8")
        return digest(block)
    update_rule = register_rule
    def validate_source_hash(self, m):
        block = self.find_rule(m["task_id"])
        return bool(block and f"- Source Hash: {m['source_hash']}\n" in block and "- Status: ACTIVE\n" in block)
    def mark_outdated(self, m): return self.register_rule(m, "OUTDATED")

class Checker:
    def __init__(self, state): self.root = Path(state).resolve()
    def cfg(self): return read(self.root / "config.json")
    @contextlib.contextmanager
    def transaction(self):
        self.root.mkdir(parents=True, exist_ok=True); lock = self.root / ".state.lock"
        try: fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError: raise ValueError(f"State busy: {lock}; investigate owner before recovery")
        try:
            os.write(fd, json.dumps({"pid": os.getpid(), "at": now()}).encode()); os.close(fd)
            yield
        finally: lock.unlink(missing_ok=True)
    def init(self, project, registry=None):
        if (self.root / "config.json").exists(): raise ValueError("Already initialized")
        project = Path(project).resolve(strict=True)
        if not project.is_dir(): raise ValueError("Project must be a directory")
        cfg = {"project": str(project), "rules_registry": str(Path(registry).resolve() if registry else project/"docs"/"rules-manager.md"),
            "version": VERSION, "max_test_context": 24000, "max_evidence_context": 12000, "max_history_context": 4000,
            "output_mode": "PROGRESS", "llm_usage_policy": "ON_DEMAND", "adapters": {}}
        write(self.root/"config.json", cfg)
        from case_inventory import install
        install(self)
        return cfg
    def task(self, task=None):
        return self.root/"tasks"/ident(task or read(self.root/"runtime"/"current_task.json")["task_id"])
    def manifest(self, task=None): return read(self.task(task)/"manifest.json")
    def run_dir(self, run, task=None): return self.task(task)/"results"/ident(run)
    def ingest(self, source, task, normalized=None, force=False):
        ident(task); source = Path(source).resolve(strict=True); sha = file_hash(source); d = self.task(task)
        old = read(d/"manifest.json") if (d/"manifest.json").exists() else None
        if old and Path(old["source"]) != source: raise ValueError("Task ID belongs to another source")
        if old and old["source_hash"] == sha and not force:
            self.sync_rules(task); write(self.root/"runtime"/"current_task.json", {"task_id":task})
            from case_inventory import materialize, install
            install(self); provision=materialize(self,task)
            return {"manifest_cache_hit": True, "full_source_reload_count": 0, "task_id":task,"testcases":provision}
        content = source.read_text(encoding="utf-8-sig")
        if normalized:
            payload = read(normalized)
            if payload.get("source_hash") != sha: raise ValueError("Normalization source hash mismatch")
        elif source.suffix.lower() == ".json": payload = json.loads(content)
        elif source.suffix.lower() in (".yaml", ".yml"):
            try: import yaml
            except ImportError: raise ValueError("PyYAML needed, or supply --normalized JSON")
            payload = yaml.safe_load(content)
        elif source.suffix.lower() == ".csv":
            rows = list(csv.DictReader(content.splitlines()))
            for index, row in enumerate(rows):
                for k in LISTS + ["source_lines", "mutating", "browser_required", "overall_timeout"]:
                    if row.get(k): row[k] = json.loads(row[k])
                    elif k in row: del row[k]
                row.setdefault("source_lines", [index+2,index+2])
            payload = {"title":source.stem, "test_cases":rows}
        else:
            return {"status":"NEEDS_NORMALIZATION", "source":str(source), "source_hash":sha,
                "instruction":"Read source once; materialize contracts with line references, then ingest --normalized JSON."}
        if not isinstance(payload, dict) or not isinstance(payload.get("test_cases"), list) or not payload["test_cases"]:
            raise ValueError("Nonempty test_cases array required")
        cases = [normalize(c, len(content.splitlines())) for c in payload["test_cases"]]
        ids = [c["test_id"] for c in cases]
        if len({s.casefold() for s in ids}) != len(ids): raise ValueError("Duplicate IDs, including case collisions")
        docs = Path(self.cfg()["project"])/"docs"
        inventory = {"docs_access":"available" if docs.is_dir() else "unavailable", "at":now(),
            "scope":"Recursive Markdown inventory; skill performs semantic reading",
            "files":[{"path":str(p), "sha256":file_hash(p)} for p in sorted(docs.rglob("*.md"))] if docs.is_dir() else []}
        m = {"task_id":task, "title":payload.get("title",source.stem), "source":str(source), "source_hash":sha,
            "domain":payload.get("domain","engineering"), "purpose":payload.get("purpose",""), "test_case_ids":ids,
            "created_at":old["created_at"] if old else now(), "updated_at":now(), "manifest_path":str(d/"manifest.json"),
            "version":VERSION, "manifest_schema_version":1, "acceptance_contract":"all mandatory checks plus evidence"}
        for k in ("global_rules","architecture_rules","required_skills","required_tools","required_views","required_outputs"):
            m[k] = strings(payload.get(k,[]),k)
        m["rule_files"] = [{"path":str(Path(p).resolve(strict=True)), "sha256":file_hash(p)} for p in payload.get("rule_files",[])]
        common_changed = bool(old and any(old.get(k) != m.get(k) for k in
            ("global_rules","architecture_rules","rule_files","required_skills","required_tools","required_views","required_outputs","version")))
        delta = {"added":[], "changed":[], "unchanged":[], "removed":sorted(set(old["test_case_ids"] if old else [])-set(ids))}
        for c in cases:
            path = d/"test_cases"/(c["test_id"]+".json"); previous = read(path) if path.exists() else None
            if previous and previous["contract_hash"] == c["contract_hash"]:
                c.update(status="OUTDATED" if common_changed else previous["status"],last_run=previous["last_run"])
                delta["changed" if common_changed else "unchanged"].append(c["test_id"])
            elif previous: c["status"]="OUTDATED"; delta["changed"].append(c["test_id"])
            else: delta["added"].append(c["test_id"])
            write(path,c)
        write(d/"manifest.json",m)
        st = source.stat()
        write(d/"source_hash.json", {"source_file":source.name,"source_path":str(source),"size":st.st_size,
            "modified_at":st.st_mtime,"sha256":sha,"ingested_at":now(),"parser_version":VERSION})
        (d/"source").mkdir(exist_ok=True); shutil.copyfile(source,d/"source"/(sha+source.suffix))
        write(d/"reports"/"ingest.json", {**delta,"docs":inventory,"full_source_reload_count":1})
        self.sync_rules(task); write(self.root/"runtime"/"current_task.json",{"task_id":task})
        from case_inventory import materialize, install
        install(self); provision=materialize(self,task)
        return {"task_id":task, **delta,"testcases":provision}
    def sync_rules(self, task=None):
        m = self.manifest(task)
        from source_discovery import resolve_reference
        if file_hash(resolve_reference(self,m["source"])) != m["source_hash"]: raise ValueError("TC_SOURCE_CHANGED")
        adapter = RulesManagerAdapter(self.cfg()["rules_registry"])
        sha = adapter.register_rule(m)
        write(self.task(task)/"rules"/"registration.json",{"registration_hash":sha,"source_hash":m["source_hash"],"at":now()})
        return {"status":"ACTIVE","registry":str(adapter.path)}
    def verify(self, task=None):
        m = self.manifest(task); issues=[]
        from source_discovery import discover, issues as source_issues, resolve_reference
        issues.extend(source_issues(discover(self)))
        if m["version"] != VERSION or m["manifest_schema_version"] != 1: issues.append("REVALIDATION_REQUIRED")
        for item in [{"path":m["source"],"sha256":m["source_hash"]}, *m["rule_files"]]:
            try:
                if file_hash(resolve_reference(self,item["path"])) != item["sha256"]:
                    issues.append("TC_SOURCE_CHANGED" if item["path"] == m["source"] else "TC_RULE_OUTDATED:"+item["path"])
            except ValueError as error: issues.append(str(error))
            except OSError: issues.append("SOURCE_UNAVAILABLE:"+item["path"])
        adapter=RulesManagerAdapter(self.cfg()["rules_registry"]); reg=read(self.task(task)/"rules"/"registration.json")
        if not adapter.validate_source_hash(m) or digest(adapter.find_rule(m["task_id"])) != reg["registration_hash"]:
            issues.append("TC_RULE_OUTDATED")
        return issues
    def revalidate(self, task=None):
        issues = [x for x in self.verify(task) if x != "REVALIDATION_REQUIRED"]
        if issues: raise ValueError("; ".join(issues))
        cases = self.select(task=task)
        if any(c["status"] == "RUNNING" for c in cases):
            raise ValueError("Finish active runs before revalidation")
        manifest = self.manifest(task)
        manifest.update(version=VERSION, updated_at=now())
        for case in cases:
            case["status"] = "OUTDATED"
            write(self.task(task)/"test_cases"/(case["test_id"]+".json"),case)
        write(self.task(task)/"manifest.json",manifest)
        self.sync_rules(task)
        return {"status":"REVALIDATED", "test_status":"OUTDATED", "version":VERSION}
    def select(self, selector="all", task=None, tag=None):
        m=self.manifest(task); cases=[read(self.task(task)/"test_cases"/(x+".json")) for x in m["test_case_ids"]]
        for c in cases:
            normalized = normalize(c, 2147483647)
            if normalized["contract_hash"] != c["contract_hash"]:
                raise ValueError("CONTRACT_INTEGRITY_ERROR: re-ingest the reviewed source")
        if tag: return [c for c in cases if tag in c["tags"]]
        if selector.lower() in ("failed","blocked","outdated"): return [c for c in cases if c["status"] == selector.upper()]
        if selector=="all": return cases
        if ".." in selector:
            first,last=selector.split("..",1); start,end=m["test_case_ids"].index(first),m["test_case_ids"].index(last)
            if start>end: raise ValueError("Reversed range")
            return cases[start:end+1]
        if ":" in selector:
            key,value=selector.split(":",1); key={"architecture":"architecture_variant"}.get(key,key)
            if key not in ("difficulty","variant","architecture_variant"): raise ValueError("Invalid selector")
            return [c for c in cases if c[key]==value]
        return [c for c in cases if c["test_id"]==selector]
    def dry_run(self, selector="all", task=None, tag=None):
        m=self.manifest(task); issues=self.verify(task); plans=[]
        for c in self.select(selector,task,tag):
            from plan_registry import resolve_case
            c=resolve_case(self,self.manifest(task)["task_id"],c)
            ctx={k:m[k] for k in ("source_hash","global_rules","architecture_rules","rule_files","required_skills","required_tools","required_views","required_outputs","version")}
            ctx["test"]=c; blockers=list(issues)
            if len(json.dumps(ctx,ensure_ascii=False))>self.cfg()["max_test_context"]: blockers.append("CONTEXT_BUDGET_EXCEEDED")
            plans.append({"context":ctx,"blockers":blockers,"preflight_required":["dependencies","application","project","permissions","test_data"]})
        return plans
    def lock_path(self): return Path(self.cfg()["project"])/".tool-checker"/"locks"/"mutation.json"
    def preflight(self, test, preflight, task=None, baseline=None):
        plans=self.dry_run(test,task)
        if len(plans)!=1: raise ValueError("Select one test per preflight")
        plan=plans[0]; c=plan["context"]["test"]; m=self.manifest(task); proof=read(preflight)
        if plan["blockers"]: raise ValueError("; ".join(plan["blockers"]))
        if proof.get("source_hash")!=m["source_hash"] or proof.get("contract_hash")!=c["contract_hash"]: raise ValueError("Preflight hash mismatch")
        if proof.get("project_path")!=self.cfg()["project"]: raise ValueError("Preflight project mismatch")
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(proof["checked_at"])).total_seconds()
        if not 0<=age<=900: raise ValueError("Preflight older than 15 minutes or future dated")
        for k in plan["preflight_required"]:
            if proof.get(k,{}).get("status")!="PASSED" or not proof[k].get("evidence"): raise ValueError("Missing observed preflight: "+k)
        for field in ("preconditions", "required_model_context"):
            observed = proof.get(field, [])
            for name in c[field]:
                if not any(x.get("name")==name and x.get("status")=="PASSED" and x.get("evidence") for x in observed):
                    raise ValueError("Missing observed " + field + ":" + name)
        for k in ("skills","tools","views"):
            if not set(c["required_"+k]+m["required_"+k])<=set(proof.get("available_"+k,[])): raise ValueError("Missing required "+k)
        if c["browser_required"] and not proof.get("browser",{}).get("observed_working"): raise ValueError("Browser not observed working")
        before=read(baseline) if baseline else None
        if c["mutating"] and (not isinstance(before,dict) or before.get("model_revision") is None or not proof.get("isolated_scope")):
            raise ValueError("Mutation requires isolated scope and baseline revision")
        return plan, c, m, proof, before
    def start(self, test, preflight, task=None, baseline=None, execution_scope="campaign"):
        from case_inventory import materialize, binding as case_binding
        durable_task=self.manifest(task)["task_id"]
        provision=materialize(self,durable_task)
        if provision['installation_conflicts']:
            raise ValueError('CLI installation conflict: '+', '.join(provision['installation_conflicts']))
        durable=case_binding(self,durable_task,test)
        from campaign_state import attached
        if execution_scope not in ("campaign", "standalone"): raise ValueError("Unknown execution scope")
        campaign = attached(self) if execution_scope == "campaign" else None
        binding = campaign.test_start(self.manifest(task)["task_id"], test) if campaign else None
        plan, c, m, proof, before = self.preflight(test, preflight, task, baseline)
        if execution_scope == "standalone" and self.lock_path().exists():
            raise ValueError("Project mutation lock held: "+str(self.lock_path()))
        run_id="run-"+uuid.uuid4().hex; lock=None
        if c["mutating"] or execution_scope == "standalone":
            lock=self.lock_path(); lock.parent.mkdir(parents=True,exist_ok=True)
            try:
                with lock.open("x",encoding="utf-8") as f: json.dump({"run_id":run_id,"task_id":m["task_id"],"state":str(self.root)},f)
            except FileExistsError: raise ValueError("Project mutation lock held: "+str(lock))
        d=self.run_dir(run_id,task)
        try:
            run={"task_id":m["task_id"],"test_id":c["test_id"],"run_id":run_id,"source_hash":m["source_hash"],
                "execution_scope":execution_scope,"config_hash":digest(self.cfg()),"contract_hash":c["contract_hash"],"testcase_revision":durable,"status":"RUNNING","started_at":now(),"finished_at":None,"context":plan["context"],
                "versions":{"tool_checker_version":VERSION,"skill_contract_version":VERSION,"manifest_schema_version":1,
                    "browser_adapter_version":"codex-mediated-1","rules_version":digest(m["rule_files"])},
                "evidence":[],"findings":[],"failures":[],"warnings":[],"completion_status":"PENDING","next_actions":[],
                "lock":str(lock) if lock else None}
            if binding:
                run["campaign"] = binding
            write(d/"result.json",run); write(d/"preflight.json",proof)
            write(d/"checkpoint.json",{"completed_steps":[],"next_step":"execute","model_revision":before.get("model_revision") if before else None})
            if before is not None: write(d/"model-before.json",before)
            stored=read(self.task(task)/"test_cases"/(c["test_id"]+".json")); stored.update(status="RUNNING",last_run=run_id); write(self.task(task)/"test_cases"/(c["test_id"]+".json"),stored)
            write(self.root/"runtime"/"current_run.json",{"task_id":m["task_id"],"run_id":run_id})
            if binding:
                campaign.bind(c["test_id"], run_id)
            return run
        except Exception:
            if lock: lock.unlink(missing_ok=True)
            raise
    def evidence(self, run_id, path, kind, task=None):
        d=self.run_dir(run_id,task); run=read(d/"result.json")
        if run["status"]!="RUNNING": raise ValueError("Run closed")
        source=Path(path).resolve(strict=True)
        if not source.is_file() or source.stat().st_size==0: raise ValueError("Nonempty evidence file required")
        if kind == "screenshot":
            with source.open("rb") as f: signature = f.read(12)
            if not (signature.startswith(b"\x89PNG\r\n\x1a\n") or signature.startswith(b"\xff\xd8\xff") or
                    (signature.startswith(b"RIFF") and signature[8:12] == b"WEBP")):
                raise ValueError("Screenshot must be a PNG, JPEG or WebP image")
        ev_id="ev-"+uuid.uuid4().hex; target=d/"evidence"/(ev_id+source.suffix); target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source,target)
        ev={"id":ev_id,"path":str(target.relative_to(d)),"sha256":file_hash(target),"kind":kind,"captured_at":now(),"original_path":str(source)}
        run["evidence"].append(ev); write(d/"result.json",run); return ev
    def checkpoint(self, run_id, path, task=None):
        d=self.run_dir(run_id,task)
        if read(d/"result.json")["status"]!="RUNNING": raise ValueError("Run closed")
        point=read(path); strings(point.get("completed_steps",[]),"completed_steps")
        if not point.get("next_step"): raise ValueError("next_step required")
        point["updated_at"]=now(); write(d/"checkpoint.json",point); return point
    def resume(self, run_id, task=None):
        d=self.run_dir(run_id,task); run=read(d/"result.json")
        if run["status"]!="RUNNING": raise ValueError("Run closed; start a new run")
        issues=self.verify(task); cases=self.select(run["test_id"],task)
        if not cases or cases[0]["contract_hash"]!=run["contract_hash"]: issues.append("CONTRACT_CHANGED")
        if run["source_hash"]!=self.manifest(task)["source_hash"]: issues.append("TC_SOURCE_CHANGED")
        if run.get("campaign"):
            from campaign_state import Campaign
            manager = Campaign(self, run["campaign"]["campaign_id"])
            campaign = manager.load()
            if campaign["state"] != f"RUN_{run['campaign']['round']}_ACTIVE":
                issues.append("CAMPAIGN_POLICY_VIOLATION: round not active")
            issues.extend(manager.drift(campaign))
        if run["lock"] and (not Path(run["lock"]).exists() or read(run["lock"]).get("run_id")!=run_id): issues.append("LOCK_LOST")
        if (datetime.now(timezone.utc)-datetime.fromisoformat(run["started_at"])).total_seconds()>run["context"]["test"]["overall_timeout"]: issues.append("TIMEOUT")
        return {"run":run,"checkpoint":read(d/"checkpoint.json"),"blockers":issues,
            "instruction":"Verify actual revision and browser session before continuing; never blindly replay a mutation."}
    def finish(self, run_id, observations, task=None):
        d=self.run_dir(run_id,task); run=read(d/"result.json")
        if run["status"]!="RUNNING": raise ValueError("Run already finalized")
        actual=read(observations)
        if actual.get("run_id")!=run_id: raise ValueError("Observations run mismatch")
        c=run["context"]["test"]; failures=[]; missing=[]; blockers=self.resume(run_id,task)["blockers"]; valid={}
        for ev in run["evidence"]:
            p=(d/ev["path"]).resolve()
            if not p.is_relative_to(d.resolve()) or not p.is_file() or file_hash(p)!=ev["sha256"]: blockers.append("EVIDENCE_INTEGRITY_ERROR")
            else: valid[ev["id"]]=ev
        def evidenced(item):
            refs=item.get("evidence",[])
            return bool(refs) and all(ref in valid for ref in refs)
        if c.get("engineering_assistant"):
            from engineering_assistant import evaluate
            assessment = evaluate(c["engineering_assistant"], actual.get("engineering_assistant"),
                                  evidenced, {x["kind"] for x in valid.values()})
            failures.extend(assessment["failures"])
            missing.extend(assessment["missing"])
            write(d/"assistant-assessment.json", assessment)
            if assessment["failures"]:
                actual.setdefault("findings", []).append({
                    "category": "AGENT_BUG", "code": "ENGINEERING_ASSISTANT_EXECUTION_DEFECT",
                    "blocking": True, "details": assessment["failures"]})
        if c.get("call_assertions"):
            from call_contract import evaluate_assertions
            call_result = evaluate_assertions(c["call_assertions"], actual.get("call_trace"), evidenced)
            failures.extend(call_result["failures"])
            missing.extend(call_result["missing"])
            write(d/"call-assessment.json", call_result)
        else:
            call_result = None
        actions=actual.get("actions",[])
        for field in ("actions", "tools", "views", "outputs", "checks"):
            failures.extend("OBSERVED_FAILURE:" + x.get("name", field) for x in actual.get(field, [])
                            if x.get("status") == "FAILED" and evidenced(x))
        observed=[x.get("name") for x in actions if x.get("status")=="PASSED" and evidenced(x)]
        cursor=0
        for name in c["required_actions"]:
            try: cursor=observed.index(name,cursor)+1
            except ValueError: missing.append("TC_WRONG_TOOL_SEQUENCE:"+name)
        for field,required in (("tools",c["required_tools"]+run["context"]["required_tools"]),
            ("views",c["required_views"]+run["context"]["required_views"]),("outputs",run["context"]["required_outputs"])):
            names=[x.get("name") for x in actual.get(field,[]) if x.get("status")=="PASSED" and evidenced(x)]
            missing.extend("REQUIRED_"+field.upper()+":"+x for x in required if x not in names)
        questions=[x.get("name") for x in actual.get("questions",[]) if evidenced(x)]
        absent=[x for x in c["expected_questions"] if x not in questions]
        forbidden=[x for x in c["forbidden_questions"] if x in questions]
        missing.extend("TC_MISSING_QUESTION:"+x for x in absent); failures.extend("TC_UNEXPECTED_QUESTION:"+x for x in forbidden)
        checks=actual.get("checks",[])
        for field in CHECKS:
            for name in c[field]:
                matches=[x for x in checks if x.get("category")==field and x.get("name")==name and evidenced(x)]
                if any(x.get("status")=="FAILED" for x in matches): failures.append(field+":"+name)
                elif not any(x.get("status")=="PASSED" for x in matches): missing.append(field+":"+name)
        for name in c["failure_conditions"]:
            matches=[x for x in checks if x.get("category")=="failure_conditions" and x.get("name")==name and evidenced(x)]
            if any(x.get("observed") is True for x in matches): failures.append("FAILURE_CONDITION:"+name)
            elif not any(x.get("observed") is False for x in matches): missing.append("UNASSESSED_FAILURE_CONDITION:"+name)
        if c["browser_required"]:
            browser=actual.get("browser",[])
            if not browser: missing.append("TC_BROWSER_ACTION_FAILED")
            for action in browser:
                if not all(action.get(k) for k in ("target","purpose","precondition","expected_effect","actual_effect","url")) or not evidenced(action):
                    missing.append("BROWSER_CLICK_CONTRACT")
                elif action.get("status")!="PASSED": failures.append("TC_BROWSER_ACTION_FAILED")
            if not any(x["kind"]=="screenshot" for x in valid.values()): missing.append("BROWSER_SCREENSHOT_MISSING")
        if c["decision_mode"]=="SCRIPTED" and (actual.get("decision_source")!="SCRIPTED_TEST" or actual.get("decision")!=c["expected_decision"]):
            missing.append("SCRIPTED_DECISION_MISSING")
        if c["mutating"]:
            after=actual.get("model_after")
            if not isinstance(after,dict) or after.get("model_revision") is None: missing.append("MODEL_AFTER_MISSING")
            else:
                before=read(d/"model-before.json"); write(d/"model-after.json",after)
                if c.get("engineering_assistant",{}).get("mutation_expected") and before == after:
                    failures.append("ASSISTANT_NO_CORE_EFFECT")
                write(d/"model-diff.json",{k:{"before":before.get(k),"after":after.get(k)} for k in sorted(before.keys()|after.keys()) if before.get(k)!=after.get(k)})
            if not any(x["kind"]=="model" for x in valid.values()): missing.append("MODEL_EVIDENCE_MISSING")
        findings=actual.get("findings",[])
        for finding in findings:
            if finding.get("category") not in CATEGORIES: raise ValueError("Invalid finding category")
            if finding.get("blocking",True): failures.append(finding.get("code","UNKNOWN"))
        if not valid: missing.append("NO_EVIDENCE")
        if actual.get("claimed_complete") and (missing or failures or blockers): failures.append("TC_PREMATURE_COMPLETION")
        if actual.get("environment_error"): blockers.append(actual["environment_error"])
        status="BLOCKED" if blockers else "FAILED" if failures else "PARTIAL" if missing else "PASSED"
        run.update(status=status,finished_at=now(),actual=actual,expected={k:c[k] for k in CHECKS+["required_actions","expected_questions","forbidden_questions"]},
            failures=failures,warnings=missing,findings=findings,completion_status="COMPLETE" if status=="PASSED" else "INCOMPLETE",
            next_actions=blockers+missing,question_metrics={"correct_question_count":len(set(questions)&set(c["expected_questions"])),
                "missing_question_count":len(absent),"unnecessary_question_count":len(forbidden)})
        if call_result is not None:
            run["expected"]["call_assertions"] = c["call_assertions"]
            run["call_assessment"] = call_result
        for name,value in (("expected-vs-actual",{"expected":run["expected"],"actual":actual}),("actions",actions),
            ("questions",actual.get("questions",[])),("tool-calls",actual.get("tools",[])),("validation",checks),("findings",findings)):
            write(d/(name+".json"),value)
        write(d/"result.json",run)
        (d/"summary.md").write_text(f"# {run['test_id']} — {status}\n\nRun: {run_id}\n\n"+"\n".join("- "+x for x in failures+blockers+missing)+f"\n\nEvidence: {len(valid)} files\n",encoding="utf-8")
        current=self.select(run["test_id"],task)
        if current and current[0]["last_run"]==run_id and current[0]["contract_hash"]==run["contract_hash"]:
            current[0]["status"]=status if run["source_hash"]==self.manifest(task)["source_hash"] else "OUTDATED"
            write(self.task(task)/"test_cases"/(run["test_id"]+".json"),current[0])
        if run["lock"]:
            lock=Path(run["lock"])
            if lock.exists() and read(lock).get("run_id")==run_id: lock.unlink()
        return {"run_id":run_id,"status":status,"failures":failures,"missing":missing,"blockers":blockers,"summary":str(d/"summary.md")}
    def baseline(self, run_id, task=None):
        d=self.run_dir(run_id,task); run=read(d/"result.json")
        if run["status"]!="PASSED": raise ValueError("Only PASS may become a baseline")
        for ev in run["evidence"]:
            if file_hash(d/ev["path"])!=ev["sha256"]: raise ValueError("Evidence integrity failure")
        target=self.task(task)/"baseline"/run["test_id"]/run_id
        if target.exists(): raise ValueError("Baseline exists")
        shutil.copytree(d,target); return {"baseline":str(target)}
    def report(self, run_id=None, task=None):
        if run_id:
            run=read(self.run_dir(run_id,task)/"result.json")
            return {k:run[k] for k in ("run_id","test_id","status","completion_status","failures","warnings","next_actions")}
        cases=self.select(task=task); groups={}
        for key in ("difficulty","architecture_variant","variant"):
            groups[key]=dict(collections.Counter(c[key] or "unspecified" for c in cases if c["status"]=="FAILED"))
        categories=collections.Counter(); skills=collections.Counter()
        for c in cases:
            if c["last_run"]:
                for finding in read(self.run_dir(c["last_run"],task)/"result.json")["findings"]:
                    categories[finding.get("category","UNKNOWN")]+=1
                    if finding.get("skill"): skills[finding["skill"]]+=1
        result={"total":len(cases),"statuses":dict(collections.Counter(c["status"] for c in cases)),
            "failure_groups":groups,"failure_categories":dict(categories),"failure_skills":dict(skills),"source_issues":self.verify(task)}
        write(self.task(task)/"reports"/"batch.json",result); return result
    def self_check(self):
        probe=self.root/"runtime"/"self-check.json"; write(probe,{"hash":digest("tool-checker")})
        return {"state_writable":read(probe)["hash"]==digest("tool-checker"),
            "hashing":hashlib.sha256(b"abc").hexdigest()=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            "project_available":Path(self.cfg()["project"]).is_dir(),
            "browser_adapter":"Requires live Codex capability check; Python does not claim it works",
            "rules_manager_adapter":"Markdown registry; validate per task with verify-source","version":VERSION}

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--state",required=True); p.add_argument("--task")
    sub=p.add_subparsers(dest="command",required=True)
    from campaign_cli import add_parser
    add_parser(sub)
    q=sub.add_parser("init"); q.add_argument("--project",required=True); q.add_argument("--registry")
    q=sub.add_parser("ingest"); q.add_argument("source"); q.add_argument("--id",required=True); q.add_argument("--normalized"); q.add_argument("--force",action="store_true")
    for name in ("status","list","verify-source","sync-rules","self-check"): sub.add_parser(name)
    q=sub.add_parser("revalidate"); q.add_argument("--reviewed",action="store_true",required=True)
    for name in ("dry-run","run"):
        q=sub.add_parser(name); q.add_argument("selector",nargs="?",default="all"); q.add_argument("--tag")
        q.add_argument("--failed",action="store_true"); q.add_argument("--outdated",action="store_true")
        if name=="run": q.add_argument("--preflight"); q.add_argument("--baseline")
    q=sub.add_parser("evidence"); q.add_argument("run_id"); q.add_argument("file")
    q.add_argument("--kind",required=True,choices=["screenshot","browser","model","backend","log","validation","other"])
    q=sub.add_parser("checkpoint"); q.add_argument("run_id"); q.add_argument("file")
    q=sub.add_parser("finish"); q.add_argument("run_id"); q.add_argument("--observations",required=True)
    for name in ("resume","baseline"):
        q=sub.add_parser(name); q.add_argument("run_id")
    q=sub.add_parser("report"); q.add_argument("run_id",nargs="?"); q.add_argument("--latest",action="store_true")
    a=p.parse_args(); tc=Checker(a.state)
    try:
        with tc.transaction():
            cmd=a.command
            if cmd=="campaign":
                from campaign_cli import dispatch
                result=dispatch(tc,a)
            elif cmd=="init": result=tc.init(a.project,a.registry)
            elif cmd=="ingest": result=tc.ingest(a.source,a.id,a.normalized,a.force)
            elif cmd=="self-check": result=tc.self_check()
            elif cmd=="verify-source": result={"issues":tc.verify(a.task)}
            elif cmd=="revalidate": result=tc.revalidate(a.task)
            elif cmd=="sync-rules": result=tc.sync_rules(a.task)
            elif cmd in ("status","list"): result=[{k:c[k] for k in ("test_id","title","status","last_run")} for c in tc.select(task=a.task)]
            elif cmd in ("dry-run","run"):
                selector="failed" if a.failed else "outdated" if a.outdated else a.selector
                if cmd=="dry-run" or not a.preflight: result=tc.dry_run(selector,a.task,a.tag)
                else:
                    chosen=tc.select(selector,a.task,a.tag)
                    if len(chosen)!=1: raise ValueError("One case per observed preflight; skill orchestrates batches")
                    result=tc.start(chosen[0]["test_id"],a.preflight,a.task,a.baseline)
            elif cmd=="evidence": result=tc.evidence(a.run_id,a.file,a.kind,a.task)
            elif cmd=="checkpoint": result=tc.checkpoint(a.run_id,a.file,a.task)
            elif cmd=="finish": result=tc.finish(a.run_id,a.observations,a.task)
            elif cmd=="resume": result=tc.resume(a.run_id,a.task)
            elif cmd=="baseline": result=tc.baseline(a.run_id,a.task)
            else:
                run_id=a.run_id
                if a.latest:
                    latest=read(tc.root/"runtime"/"current_run.json"); run_id=latest["run_id"]
                    if a.task and a.task!=latest["task_id"]: raise ValueError("Latest run belongs to another task")
                    a.task=latest["task_id"]
                result=tc.report(run_id,a.task)
        print(json.dumps(result,indent=2,ensure_ascii=False)); return 0
    except (ValueError,OSError,KeyError,TypeError) as e:
        print(json.dumps({"error":str(e)},ensure_ascii=False),file=sys.stderr); return 2
if __name__=="__main__": sys.exit(main())
