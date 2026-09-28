#!/usr/bin/env python3
"""Deterministic background worker and job API for Tool Checker."""
from __future__ import annotations
import argparse
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone

from tool_check import Checker, CHECKS, digest, file_hash, ident, now, read, write
from progress_model import MODES, POLICIES, TERMINAL, plan_for, event, public_job, batch_progress, positive

class Cancelled(Exception): pass
class StepFailed(Exception): pass

class Jobs:
    def __init__(self, state):
        self.tc = Checker(state)
        self.root = self.tc.root / "jobs"
        self.children = []

    def directory(self, job_id):
        return self.root / ident(job_id)

    def load(self, job_id):
        return read(self.directory(job_id) / "job.json")

    @contextlib.contextmanager
    def state_lock(self):
        for attempt in range(100):
            try:
                manager = self.tc.transaction()
                manager.__enter__()
                break
            except ValueError as error:
                if not str(error).startswith("State busy:") or attempt == 99:
                    raise
                time.sleep(.05)
        try:
            yield
        finally:
            manager.__exit__(None, None, None)

    def emit(self, job, kind, step=None):
        update = event(job, kind, step)
        job.update(phase=update["phase"], step_id=update["step_id"], current_step=update["step_label"],
                   completed_steps=update["completed_steps"], total_steps=update["total_steps"],
                   percentage=update["percentage"], updated_at=update["timestamp"])
        job["cancel_requested"] = (self.directory(job["job_id"])/"cancel.json").exists()
        directory = self.directory(job["job_id"])
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(update, ensure_ascii=False)+"\n")
            f.flush()
        write(directory/"job.json", job)
        # One pointer to the most recently updated run; authoritative per-job state remains in jobs/.
        write(self.tc.root/"runtime"/"current_run.json", public_job(job))
        return update

    def submit(self, task, test, preflight, baseline=None, mode=None, llm_policy=None,
               queued=False, batch_id=None, test_weight=1, execution_scope="campaign", automated_e2e=False):
        if execution_scope not in ("campaign", "standalone"): raise ValueError("Unknown execution scope")
        if type(automated_e2e) is not bool: raise ValueError("Invalid E2E automation policy")
        from case_inventory import materialize, binding
        provision=materialize(self.tc,task)
        if provision['installation_conflicts']:
            raise ValueError('CLI installation conflict: '+', '.join(provision['installation_conflicts']))
        durable=binding(self.tc,task,test)
        cfg = self.tc.cfg()
        mode = (mode or cfg.get("output_mode","PROGRESS")).upper()
        policy = (llm_policy or cfg.get("llm_usage_policy","ON_DEMAND")).upper()
        if mode not in MODES or policy not in POLICIES:
            raise ValueError("Unknown output mode or LLM policy")
        if not positive(test_weight):
            raise ValueError("Invalid test weight")
        with self.state_lock():
            cases = self.tc.select(test, task)
            if len(cases) != 1:
                raise ValueError("One case per job")
            from plan_registry import resolve_case
            case = resolve_case(self.tc,task,cases[0])
            from plan_registry import effective_llm_policy
            policy = effective_llm_policy(case,cfg,llm_policy)
            from plan_registry import bind_parameters
            plan_for(case)
            case=bind_parameters(case,cfg)
            plan, phase_weights = plan_for(case)
            adapters = cfg.get("adapters",{})
            for step in plan:
                if step.get("kind") == "adapter":
                    adapter = adapters.get(step["adapter"])
                    if not adapter:
                        raise ValueError("Adapter not configured: "+step["adapter"])
                    if policy == "DISABLED" and adapter.get("uses_llm") is not False:
                        raise ValueError("DISABLED requires explicitly non-LLM adapters")
                    if type(adapter.get("mutating")) is not bool or (adapter["mutating"] and not case["mutating"]):
                        raise ValueError("Adapter mutation scope conflicts with test contract")
            _, _, manifest, proof, before = self.tc.preflight(test, preflight, task, baseline)
            job_id = "job-"+uuid.uuid4().hex
            job = {"job_id":job_id,"task_id":task,"test_id":test,"run_id":None,"testcase_revision":durable,
                   "plan_binding":case.get("plan_binding"),"execution_scope":execution_scope,"config_hash":digest(cfg),"status":"QUEUED","plan":plan,"phase_weights":phase_weights,
                   "automated_e2e":automated_e2e,
                   "weighted":case.get("weighted_progress",True),"completed_step_ids":[],
                   "output_mode":mode,"llm_usage_policy":policy,"batch_id":batch_id,"test_weight":test_weight,
                   "started_at":None,"updated_at":now(),"finished_at":None,"result_ref":None,
                   "decision":None,"message":"","metrics":{"llm_calls_ingest":None,"llm_calls_execution":0,
                   "llm_calls_reasoning":0,"llm_calls_visualization":0,"llm_calls_progress":0,
                   "measurement_scope":"background worker; prior Codex ingest not measured"},
                   "contract_hash":case["contract_hash"],"source_hash":manifest["source_hash"],
                   "overall_timeout":case["overall_timeout"],"queued_at":now(),
                   "adapters":{k:adapters[k] for k in {s["adapter"] for s in plan if s.get("kind")=="adapter"}}}
            write(self.directory(job_id)/"preflight.json", proof)
            if before is not None: write(self.directory(job_id)/"baseline.json", before)
            self.emit(job,"JOB_QUEUED")
        if not queued:
            try: self.launch(job_id)
            except Exception as error:
                error.job_id = job_id
                raise
        return public_job(self.load(job_id))

    def launch(self, job_id):
        job = self.load(job_id)
        if job["status"] != "QUEUED":
            raise ValueError("Only queued jobs can start")
        directory = self.directory(job_id)
        claim = directory/"launch.claim"
        try:
            with claim.open("x",encoding="utf-8") as f:
                f.write(now())
        except FileExistsError:
            raise ValueError("Job already launching")
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        try:
            with (directory/"worker.log").open("ab") as output:
                child = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--state",str(self.tc.root),
                                  "worker",job_id],stdin=subprocess.DEVNULL,stdout=output,stderr=output,
                                 creationflags=flags,start_new_session=os.name!="nt",close_fds=True)
                self.children = [p for p in self.children if p.poll() is None]
                self.children.append(child)
        except Exception:
            claim.unlink(missing_ok=True)
            raise
        return {"job_id":job_id,"status":"QUEUED"}

    def view(self, job_id):
        job = self.load(job_id)
        job["cancel_requested"] = (self.directory(job_id)/"cancel.json").exists()
        return public_job(job)

    def list(self):
        return sorted([self.view(p.parent.name) for p in self.root.glob("*/job.json")],
                      key=lambda j:j["updated_at"],reverse=True)

    def cancel(self, job_id):
        job = self.load(job_id)
        if job["status"] in TERMINAL:
            return public_job(job)
        write(self.directory(job_id)/"cancel.json", {"status":"CANCEL_REQUESTED","at":now()})
        if job["status"] == "QUEUED":
            try: self.launch(job_id)
            except ValueError: pass
        return {"job_id":job_id,"status":"CANCEL_REQUESTED",
                "message":"Stop after the current atomic operation; no process termination."}

    def answer(self, job_id, step_id, choice):
        job = self.load(job_id)
        if job["status"] != "WAITING_FOR_USER" or job["decision"]["step_id"] != step_id:
            raise ValueError("No matching pending decision")
        if choice not in job["decision"]["options"]:
            raise ValueError("Choice not in saved decision contract")
        path = self.directory(job_id)/("answer-"+ident(step_id)+".json")
        with path.open("x",encoding="utf-8") as f:
            json.dump({"step_id":step_id,"choice":choice,"at":now(),"decision_source":"INTERACTIVE"},f)
        return {"job_id":job_id,"status":"ANSWER_RECEIVED"}

    def details(self, job_id):
        job = self.load(job_id)
        d = self.directory(job_id)
        result = read(self.tc.run_dir(job["run_id"],job["task_id"])/"result.json") if job["run_id"] else {"status":job["status"],"evidence":[]}
        logs = {}
        for path in d.glob("*.log"):
            with path.open("rb") as handle:
                handle.seek(max(0, path.stat().st_size - 24000))
                logs[path.name] = handle.read().decode("utf-8", errors="replace")
        return {"job":job,"result":result,
                "logs":logs,"events":[json.loads(s) for s in (d/"events.jsonl").read_text(encoding="utf-8").splitlines()]}

    def batch(self, batch_id):
        selected = [j for j in self.list() if j["batch_id"] == batch_id]
        if not selected: raise ValueError("Unknown batch")
        return {"batch_id":batch_id,**batch_progress(selected),"jobs":selected}

    def submit_batch(self, bundle, queued=False):
        batch_id="batch-"+uuid.uuid4().hex
        created=[]
        # Deliberately queue all before launch; each gets independently verified preflight.
        try:
            for item in bundle["tests"]:
                created.append(self.submit(item["task_id"],item["test_id"],item["preflight"],
                    item.get("baseline"),item.get("output_mode"),item.get("llm_usage_policy"),
                    True,batch_id,item.get("test_weight",1)))
        except Exception:
            for item in created: self.cancel(item["job_id"])
            raise
        if not queued:
            for item in created: self.launch(item["job_id"])
        return self.batch(batch_id)

    def check_stop(self, job):
        if job.get("execution_scope")=="standalone" and digest(self.tc.cfg())!=job.get("config_hash"):
            raise ValueError("Configuration changed during independent run")
        from plan_registry import resolve_case
        current=resolve_case(self.tc,job["task_id"],self.tc.select(job["test_id"],job["task_id"])[0])
        if current.get("plan_binding")!=job.get("plan_binding"):
            raise ValueError("Reviewed plan binding changed during run")
        if (self.directory(job["job_id"])/"cancel.json").exists():
            raise Cancelled("Vom Nutzer abgebrochen")
        if not job["run_id"]:
            if (datetime.now(timezone.utc)-datetime.fromisoformat(job["queued_at"])).total_seconds() > job["overall_timeout"]:
                raise TimeoutError("Queue timeout")
            return
        run = read(self.tc.run_dir(job["run_id"],job["task_id"])/"result.json")
        if (datetime.now(timezone.utc)-datetime.fromisoformat(run["started_at"])).total_seconds() > run["context"]["test"]["overall_timeout"]:
            raise TimeoutError("Test timeout at safe operation boundary")
        issues = self.tc.resume(job["run_id"],job["task_id"])["blockers"]
        if issues: raise ValueError("; ".join(issues))

    def register(self, job, path, kind):
        with self.state_lock():
            return self.tc.evidence(job["run_id"],path,kind,job["task_id"])["id"]

    def execute(self, job, step, observations):
        directory=self.directory(job["job_id"]); case=read(self.tc.run_dir(job["run_id"],job["task_id"])/"result.json")["context"]["test"]
        kind=step["kind"]; success=True; data={}; refs=[]
        timeout=step.get("timeout",30)
        if not positive(timeout): raise ValueError("Invalid operation timeout")
        if kind in ("file","json"):
            path=Path(step["path"])
            if not path.is_absolute(): path=Path(self.tc.cfg()["project"])/path
            if not path.is_file(): raise FileNotFoundError(path)
            data={"path":str(path),"sha256":file_hash(path),"size":path.stat().st_size}
            if kind=="json":
                value=read(path)
                for part in step.get("pointer",[]):
                    value=value[part]
                data.update(actual=value,expected=step["equals"])
                success=value==step["equals"]
            elif "sha256" in step:
                success=data["sha256"]==step["sha256"]
            if path.stat().st_size:
                refs.append(self.register(job,path,"backend"))
        elif kind=="http":
            url=step["url"]
            if not url.startswith(("http://","https://")): raise ValueError("HTTP(S) required")
            try:
                response=urllib.request.urlopen(url,timeout=timeout)
            except urllib.error.HTTPError as error:
                response=error
            with response:
                body=response.read(8*1024*1024+1)
                if len(body)>8*1024*1024: raise ValueError("HTTP evidence exceeds 8 MiB")
                data={"url":url,"status":response.status,"body":body.decode("utf-8",errors="replace")}
            success=data["status"]==step.get("expected_status",200)
            if "contains" in step: success=success and step["contains"] in data["body"]
        elif kind=="decision":
            if case["decision_mode"]=="SCRIPTED":
                choice=case["expected_decision"]
                if choice not in step["options"]: raise ValueError("Scripted decision outside options")
                observations.update(decision=choice,decision_source="SCRIPTED_TEST")
            elif job.get("automated_e2e"):
                raise ValueError("Automated E2E cannot infer an answer to an original interactive decision: "+step["question"])
            else:
                job.update(status="WAITING_FOR_USER",decision={"step_id":step["step_id"],"question":step["question"],"options":step["options"]})
                self.emit(job,"WAITING_FOR_USER",step)
                answer=directory/("answer-"+step["step_id"]+".json")
                while not answer.exists():
                    self.check_stop(job); time.sleep(.2)
                choice=read(answer)["choice"]
                observations.update(decision=choice,decision_source="INTERACTIVE")
                job.update(status="RUNNING",decision=None)
                self.emit(job,"DECISION_RECEIVED",step)
            data={"question":step["question"],"choice":choice,"decision_source":observations["decision_source"]}
            if "continue_on" in step and choice not in step["continue_on"]:
                raise Cancelled("Entscheidung: " + choice)
        elif kind in ("adapter","browser"):
            adapter=job["adapters"][step["adapter"]] if kind=="adapter" else {"argv":[],"mutating":case["mutating"],"uses_llm":False}
            if kind=="browser":
                import importlib.util
                runner_path=Path(__file__).resolve().parents[1]/"adapters"/"browser_runner.py"
                spec=importlib.util.spec_from_file_location("tool_checker_browser_runner",runner_path)
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                self._owned_browser_module=module
                data=module.execute({"step":step,"run_id":job["run_id"],"job_id":job["job_id"],"project":self.tc.cfg()["project"],
                    "output_directory":str(directory),"llm_usage_policy":job["llm_usage_policy"],"atomic_mutation":case["mutating"]})
            else:
                argv=adapter.get("argv")
                if not isinstance(argv,list) or not argv or any(not isinstance(x,str) for x in argv):
                    raise ValueError("Registered adapter needs an argv array, never a shell string")
                request=directory/(step["step_id"]+"-request.json")
                write(request,{"step":step,"run_id":job["run_id"],"job_id":job["job_id"],"project":self.tc.cfg()["project"],
                               "output_directory":str(directory),"decision":observations.get("decision"),
                               "interactive_decision_bridge":1 if case["decision_mode"]=="INTERACTIVE" else None,
                               "automated_e2e":job.get("automated_e2e",False),
                               "llm_usage_policy":job["llm_usage_policy"],"atomic_mutation":adapter["mutating"]})
                output=directory/(step["step_id"]+"-stdout.json"); errors=directory/(step["step_id"]+"-stderr.log")
                # Cancellation does not terminate atomic operations. Mutating adapters have no forced timeout.
                with request.open("rb") as stdin, output.open("wb") as stdout, errors.open("wb") as stderr:
                    child=subprocess.Popen(argv,stdin=stdin,stdout=stdout,stderr=stderr,cwd=self.tc.cfg()["project"],
                        shell=False,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
                    decision_sequence=0
                    started=time.monotonic()
                    while child.poll() is None:
                        pending=directory/(f"adapter-decision-{decision_sequence+1}.json")
                        if pending.exists():
                            if job.get("automated_e2e"):
                                raise ValueError("Automated E2E adapter attempted to request a user decision")
                            if case["decision_mode"]!="INTERACTIVE":
                                raise ValueError("Scripted adapter requested an interactive decision")
                            decision=read(pending)
                            options=decision.get("options")
                            if (decision.get("sequence")!=decision_sequence+1 or
                                not isinstance(decision.get("question"),str) or not decision["question"].strip() or
                                not isinstance(options,list) or len(options)<2 or
                                any(not isinstance(x,str) or not x for x in options) or len(set(options))!=len(options)):
                                raise ValueError("Invalid adapter decision request")
                            decision_sequence+=1
                            decision_step=f"{step['step_id']}-decision-{decision_sequence}"
                            job.update(status="WAITING_FOR_USER",decision={"step_id":decision_step,
                                "question":decision["question"],"options":options,
                                "proposal":decision.get("proposal"),"revision":decision.get("revision")})
                            self.emit(job,"WAITING_FOR_USER",step)
                            answer=directory/("answer-"+decision_step+".json")
                            while not answer.exists():
                                self.check_stop(job)
                                if child.poll() is not None: raise RuntimeError("Adapter exited while awaiting decision")
                                time.sleep(.2)
                            saved=read(answer)
                            if saved.get("choice") not in options or saved.get("decision_source")!="INTERACTIVE":
                                raise ValueError("Invalid interactive adapter answer")
                            observations["questions"].append({"name":decision["question"],
                                "choice":saved["choice"],"decision_source":"INTERACTIVE",
                                "revision":decision.get("revision"),
                                "evidence":[self.register(job,pending,"validation"),self.register(job,answer,"validation")]})
                            job.update(status="RUNNING",decision=None)
                            self.emit(job,"DECISION_RECEIVED",step)
                        self.check_stop(job)
                        if not adapter["mutating"] and time.monotonic()-started>timeout:
                            raise TimeoutError("Adapter timeout")
                        time.sleep(.2)
                    returncode=child.returncode
                if returncode:
                    raise RuntimeError(f"Adapter failed with exit code {returncode}; details in local log")
                if output.stat().st_size>8*1024*1024: raise ValueError("Adapter result exceeds 8 MiB")
                data=read(output)
            calls=data.get("llm_calls",0 if adapter.get("uses_llm") is False else None)
            if calls is None:
                job["metrics"]["llm_calls_execution"]=None
            elif type(calls) is not int or calls<0: raise ValueError("Invalid LLM usage count")
            elif job["metrics"]["llm_calls_execution"] is not None:
                job["metrics"]["llm_calls_execution"]+=calls
            if job["llm_usage_policy"]=="DISABLED" and calls!=0:
                raise ValueError("Adapter violated DISABLED LLM policy")
            remap={}
            for evidence in data.get("evidence",[]):
                remap[evidence["ref"]]=self.register(job,evidence["path"],evidence["kind"])
            extra=data.get("observations",{})
            for field in ("actions","tools","views","outputs","questions","checks","browser","findings"):
                for item in extra.get(field,[]):
                    item=dict(item)
                    item["evidence"]=[remap[r] for r in item.get("evidence",[])]
                    observations.setdefault(field,[]).append(item)
            if "engineering_assistant" in extra:
                if "engineering_assistant" in observations:
                    raise ValueError("Duplicate Engineering Assistant assessment")
                assessment=dict(extra["engineering_assistant"])
                assessment["evidence"]=[remap.get(r,r) for r in assessment.get("evidence",[])]
                assessment["checks"]=[dict(check, evidence=[remap.get(r,r) for r in check.get("evidence",[])])
                                      for check in assessment.get("checks",[])]
                observations["engineering_assistant"]=assessment
            if "model_after" in extra: observations["model_after"]=extra["model_after"]
            if "call_trace" in extra:
                if "call_trace" in observations:
                    raise ValueError("Multiple full call traces require one explicit aggregate adapter")
                trace=dict(extra["call_trace"])
                trace["evidence"]=[remap[r] for r in trace.get("evidence",[])]
                trace["calls"]=[{**call,"evidence":[remap[r] for r in call.get("evidence",[])]} for call in trace.get("calls",[])]
                observations["call_trace"]=trace
            success=data.get("status")=="PASSED"
            refs.extend(remap.values())
        path=directory/(step["step_id"]+"-result.json")
        # An observed adapter prerequisite/decision block is not a failed expectation.
        blocked_adapter = kind == "adapter" and data.get("status") == "BLOCKED"
        state = "BLOCKED" if blocked_adapter else "PASSED" if success else "FAILED"
        write(path,{"step_id":step["step_id"],"status":state,"timestamp":now(),"data":data})
        refs.append(self.register(job,path,"validation"))
        if kind=="decision":
            observations["questions"].append({"name":step.get("question_name",step["question"]),"evidence":refs})
        if step.get("action"):
            observations["actions"].append({"name":step["action"],"status":state,"evidence":refs})
        if step.get("tool"):
            observations["tools"].append({"name":step["tool"],"status":state,"evidence":refs})
        if kind != "adapter":
            for check in step.get("checks",[]):
                if check.get("category") not in CHECKS: raise ValueError("Unsupported deterministic check category")
                observations["checks"].append({"name":check["name"],"category":check["category"],"status":state,"evidence":refs})
        write(directory/"observations.json",observations)
        if blocked_adapter:
            reason = data.get("reason")
            raise RuntimeError("Adapter BLOCKED: " + (reason[:2048] if isinstance(reason,str) and reason else step["step_label"]))
        if not success: raise StepFailed("Prüfung fehlgeschlagen: "+step["step_label"])

    def work(self, job_id):
        directory=self.directory(job_id); claim=directory/"worker.claim"
        try:
            with claim.open("x",encoding="utf-8") as f: f.write(str(os.getpid()))
        except FileExistsError: return
        job=self.load(job_id)
        if job["status"]!="QUEUED": return
        job.update(status="RUNNING",started_at=now(),pid=os.getpid())
        observations={"run_id":job["run_id"],"actions":[],"tools":[],"views":[],"outputs":[],"questions":[],"checks":[],"browser":[],"findings":[]}
        try:
            self.check_stop(job)
            while job["run_id"] is None:
                try:
                    with self.state_lock():
                        case = self.tc.select(job["test_id"], job["task_id"])[0]
                        if case["contract_hash"] != job["contract_hash"]:
                            raise ValueError("Contract changed while queued")
                        baseline=directory/"baseline.json"
                        run=self.tc.start(job["test_id"],directory/"preflight.json",job["task_id"],baseline if baseline.exists() else None,execution_scope=job.get("execution_scope","campaign"))
                        job["run_id"]=run["run_id"]
                        observations["run_id"]=run["run_id"]
                except ValueError as error:
                    if job.get("execution_scope")=="standalone" or not str(error).startswith("Project mutation lock held:"): raise
                    job["status"]="QUEUED"
                    job["message"]="Warte auf freien Testbereich"
                    self.emit(job,"SCOPE_WAIT")
                    self.check_stop(job)
                    time.sleep(.2)
            job.update(status="RUNNING",message="")
            job["completed_step_ids"].append("_preflight"); self.emit(job,"JOB_STARTED",job["plan"][0])
            for step in job["plan"][1:-2]:
                self.check_stop(job)
                prefix="BROWSER" if step.get("channel")=="browser" else "TOOL"
                self.emit(job,prefix+"_STARTED",step)
                self.execute(job,step,observations)
                job["completed_step_ids"].append(step["step_id"])
                self.emit(job,prefix+"_SUCCEEDED",step)
                with self.state_lock():
                    point=directory/"checkpoint.json"
                    write(point,{"completed_steps":job["completed_step_ids"],"next_step":"next plan operation","job_id":job_id})
                    self.tc.checkpoint(job["run_id"],point,job["task_id"])
            self.check_stop(job)
            job["completed_step_ids"].append("_evidence")
            self.emit(job,"EVIDENCE_SAVED",job["plan"][-2])
            observations["metrics"]=job["metrics"]
            write(directory/"observations.json",observations)
            self.emit(job,"COMPLETION_STARTED",job["plan"][-1])
            with self.state_lock():
                result=self.tc.finish(job["run_id"],directory/"observations.json",job["task_id"])
            job["completed_step_ids"].append("_completion")
            job["status"]={"PASSED":"COMPLETE","FAILED":"FAILED","BLOCKED":"BLOCKED","PARTIAL":"BLOCKED"}[result["status"]]
            job["message"]="Abgeschlossen" if job["status"]=="COMPLETE" else "Prüfung unvollständig oder fehlgeschlagen"
            job["result_ref"]=result["summary"]
        except (Exception,KeyboardInterrupt) as error:
            if isinstance(error,KeyboardInterrupt):error=Cancelled("Vom Nutzer abgebrochen")
            with (directory/"worker.log").open("a",encoding="utf-8") as f: f.write(traceback.format_exc())
            job["status"]="CANCELLED" if isinstance(error,Cancelled) else "FAILED" if isinstance(error,StepFailed) else "BLOCKED"
            job["message"]=str(error)
            observations["metrics"]=job["metrics"]
            if isinstance(error,StepFailed):
                observations["findings"].append({"code":"TC_EXPECTATION_MISMATCH","category":"EXPECTATION_MISMATCH","blocking":True,"detail":str(error)})
            else: observations["environment_error"]=str(error)
            write(directory/"observations.json",observations)
            try:
                if job["run_id"]:
                    with self.state_lock():
                        result=self.tc.finish(job["run_id"],directory/"observations.json",job["task_id"])
                        job["result_ref"]=result["summary"]
            except Exception:
                with (directory/"worker.log").open("a",encoding="utf-8") as f: f.write(traceback.format_exc())
                job["message"]+="; Ergebnisabschluss offen – lokalen Lock vor weiterer Mutation prüfen"
            self.emit(job,"TOOL_FAILED")
        browser_module=getattr(self,'_owned_browser_module',None)
        if browser_module is not None:
            try:browser_module.close_session(job_id)
            except Exception:
                with (directory/"worker.log").open("a",encoding="utf-8") as f:f.write(traceback.format_exc())
                job['browser_cleanup_pending']=True
                job['message']+='; eigene Browser-Sitzung konnte nicht geschlossen werden'
            finally:self._owned_browser_module=None
        job.update(finished_at=now(),decision=None)
        self.emit(job,"JOB_"+job["status"])
        claim.unlink(missing_ok=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state",required=True)
    subs=parser.add_subparsers(dest="command",required=True)
    p=subs.add_parser("submit"); p.add_argument("--task",required=True); p.add_argument("--test",required=True)
    p.add_argument("--preflight",required=True); p.add_argument("--baseline"); p.add_argument("--mode",choices=sorted(MODES))
    p.add_argument("--llm-policy",choices=sorted(POLICIES)); p.add_argument("--queued",action="store_true")
    p=subs.add_parser("batch-submit"); p.add_argument("bundle"); p.add_argument("--queued",action="store_true")
    for cmd in ("start","worker","status","details","cancel","batch"):
        p=subs.add_parser(cmd); p.add_argument("job_id")
    p=subs.add_parser("answer"); p.add_argument("job_id"); p.add_argument("--step",required=True); p.add_argument("--choice",required=True)
    subs.add_parser("list")
    p=subs.add_parser("serve"); p.add_argument("--port",type=int,default=18764)
    a=parser.parse_args(); jobs=Jobs(a.state)
    try:
        if a.command=="worker": jobs.work(a.job_id); return 0
        if a.command=="serve":
            from progress_server import serve
            serve(jobs,a.port); return 0
        if a.command=="submit": result=jobs.submit(a.task,a.test,a.preflight,a.baseline,a.mode,a.llm_policy,a.queued)
        elif a.command=="batch-submit": result=jobs.submit_batch(read(a.bundle),a.queued)
        elif a.command=="start": result=jobs.launch(a.job_id)
        elif a.command=="status": result=jobs.view(a.job_id)
        elif a.command=="details": result=jobs.details(a.job_id)
        elif a.command=="cancel": result=jobs.cancel(a.job_id)
        elif a.command=="answer": result=jobs.answer(a.job_id,a.step,a.choice)
        elif a.command=="batch": result=jobs.batch(a.job_id)
        else: result=jobs.list()
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps({"status":"BLOCKED","error":str(error)},ensure_ascii=False),file=sys.stderr); return 2

if __name__=="__main__": sys.exit(main())
