#!/usr/bin/env python3
"""Deterministic adapter for an already installed agent-browser CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

def main():
    request=json.load(sys.stdin)
    step=request["step"]
    command=os.environ.get("TOOL_CHECKER_AGENT_BROWSER") or shutil.which("agent-browser")
    if not command:
        raise RuntimeError("agent-browser is not installed/configured; no browser action was executed")
    session=request["job_id"]
    operation=step["browser_action"]
    allowed={"navigate":"open","click":"click","double_click":"dblclick","type":"type","clear":"fill",
             "fill":"fill","select":"select","inspect":"snapshot","screenshot":"screenshot","close":"close"}
    if operation not in allowed:
        raise ValueError("Unsupported browser action")
    output=Path(request["output_directory"])
    argv=[command,"--session",session,allowed[operation]]
    if operation=="navigate":
        if not step.get("url","").startswith(("http://","https://")): raise ValueError("HTTP(S) URL required")
        argv.append(step["url"])
    elif operation in ("click","double_click","type","clear","fill","select"):
        argv.append(step["target"])
        if operation in ("type","fill","select"): argv.append(step["value"])
        if operation=="clear": argv.append("")
    screenshot=output/(step["step_id"]+".png")
    if operation=="screenshot": argv.append(str(screenshot))
    def call(arguments):
        result=subprocess.run(arguments,capture_output=True,text=True,encoding="utf-8",errors="replace",
            shell=False,timeout=None if request.get("atomic_mutation") else step.get("timeout",30),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        if result.returncode: raise RuntimeError(result.stderr or result.stdout)
        return result.stdout
    before=step.get("precondition","According to reviewed plan")
    action_result=call(argv)
    observation=action_result if operation in ("close","inspect") else call([command,"--session",session,"snapshot"])
    url=step.get("url")
    if operation!="close": url=call([command,"--session",session,"get","url"]).strip()
    if operation not in ("close","screenshot"):
        call([command,"--session",session,"screenshot",str(screenshot)])
    expected=step.get("expected_text")
    # Mutating browser actions require observable postconditions, not CLI success alone.
    passed=bool(expected and expected in observation) if operation not in ("close","screenshot") else True
    evidence_file=output/(step["step_id"]+"-browser.txt")
    evidence_file.write_text(json.dumps({"operation":operation,"url":url,"action_result":action_result,
        "observed":observation,"expected":expected},ensure_ascii=False,indent=2),encoding="utf-8")
    evidence=[{"ref":"browser","path":str(evidence_file),"kind":"browser"}]
    if screenshot.exists(): evidence.append({"ref":"screenshot","path":str(screenshot),"kind":"screenshot"})
    refs=[x["ref"] for x in evidence]
    browser={"target":step.get("target",url or "browser"),"purpose":step["step_label"],"precondition":before,
        "expected_effect":expected or operation,"actual_effect":observation or operation,"url":url or "closed",
        "status":"PASSED" if passed else "FAILED","evidence":refs}
    print(json.dumps({"status":"PASSED" if passed else "FAILED","llm_calls":0,"evidence":evidence,
        "observations":{"browser":[browser]}},ensure_ascii=False))

if __name__=="__main__":
    try: main()
    except Exception as error:
        print(str(error),file=sys.stderr)
        sys.exit(2)
