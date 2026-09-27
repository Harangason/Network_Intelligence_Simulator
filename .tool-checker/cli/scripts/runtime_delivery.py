"""Registered deployment commands and fresh runtime probes; called only in Repair Phase."""
import json, subprocess, uuid
from pathlib import Path
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.parse import urlsplit
from tool_check import read,write,file_hash,now
TYPES={"docker","docker_compose","python_process","waitress","flask","uvicorn","node","nextjs","frontend_build","windows_service","linux_service","executable"}
RESTARTS={"NO_RESTART","HOT_RELOAD","SERVICE_RESTART","CONTAINER_RESTART","FULL_STACK_RESTART"}

def require(condition,message):
    if not condition:raise ValueError(message)
def ref(path):
    p=Path(path).resolve(strict=True)
    require(p.is_file() and p.stat().st_size>0,"Nonempty runtime evidence required")
    return {"path":str(p),"sha256":file_hash(p)}
def intact(r):
    try:return file_hash(r["path"])==r["sha256"]
    except (OSError,KeyError,TypeError):return False

def matches(expected,actual):
    if isinstance(expected,dict):return isinstance(actual,dict) and all(k in actual and matches(v,actual[k]) for k,v in expected.items())
    return type(expected) is type(actual) and expected==actual

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError("Runtime probe redirect denied")
def fetch(url):
    parts=urlsplit(url)
    require(parts.scheme in ("http","https") and parts.hostname and not parts.username and not parts.password,"Invalid configured runtime URL")
    with build_opener(ProxyHandler({}),NoRedirect()).open(url,timeout=10) as response:
        raw=response.read(1048577)
        require(len(raw)<=1048576,"Runtime probe response too large")
        result=json.loads(raw)
    require(isinstance(result,dict),"Runtime probe must return an object")
    return result

def profile(cfg,name):
    p=cfg.get("deployment_profiles",{}).get(name)
    require(isinstance(p,dict),"Registered DeploymentProfile required")
    require(p.get("runtime_type") in TYPES and p.get("restart_policy") in RESTARTS,"Unsupported runtime/restart profile")
    require(p.get("affected_services") and p.get("health_expected"),"Affected services and explicit health contract required")
    return p

def observe(p,expected):
    require(isinstance(expected,dict) and expected.get("build_id") and expected.get("commit_id"),"Expected immutable build/commit identity required")
    version=fetch(p["version_url"]);health=fetch(p["health_url"])
    return {"at":now(),"fingerprint":version,"health":health,
            "version_match":matches(expected,version),"healthy":matches(p["health_expected"],health)}

def snapshot(cfg,build):
    if build.get("runtime_profile"):
        p=profile(cfg,build["runtime_profile"])
        expected=build.get("expected_runtime_version",{})
        observed=observe(p,expected)
        require(observed["version_match"],"RUNTIME_VERSION_MISMATCH")
        require(observed["healthy"],"RUNTIME_HEALTH_FAILED")
        return {"profile":p,"profile_name":build["runtime_profile"],"expected":expected,"observed":observed}
    require(isinstance(build.get("runtime_not_applicable"),str) and build["runtime_not_applicable"].strip(),"Runtime profile or justified offline scope required")
    return {"not_applicable":build["runtime_not_applicable"]}

def drift(frozen):
    if "not_applicable" in frozen:return []
    try:
        current=observe(frozen["profile"],frozen["expected"])
        # Stable fingerprint fields only; volatile request timestamps must not be returned as version identity.
        prior=frozen["observed"]["fingerprint"]
        changed=any(current["fingerprint"].get(k)!=prior.get(k) for k in ("build_id","commit_id","components","component_versions","config_hash","schema_version","started_at","runtime_started_at","skill_version"))
        return (["RUNTIME_DRIFT"] if changed or not current["version_match"] else [])+([] if current["healthy"] else ["RUNTIME_HEALTH_FAILED"])
    except (ValueError,OSError,KeyError):return ["RUNTIME_UNVERIFIED"]

def verify_retest(result,expected,required):
    require(result.get("mode")=="real_runtime" and result.get("status")=="PASSED","TARGETED_RUNTIME_RETEST_FAILED")
    require(matches(expected,result.get("runtime_fingerprint")),"Retest ran on another version")
    checks=result.get("checks",{})
    require(required and all(checks.get(k)=="PASSED" for k in required),"Missing required runtime/browser/assistant checks")
    require(result.get("evidence") and all(intact(r) for r in result["evidence"]),"NO_RUNTIME_EVIDENCE")

def execute(cfg,plan,directory):
    policy=read(Path(__file__).resolve().parent.parent/"config/runtime-delivery-policy.json")
    require(policy.get("allow_automatic_deploy") is True,"Automatic deployment disabled by policy")
    if plan.get("restart_required"):
        require(policy.get("allow_automatic_restart") is True,"Automatic restart disabled by policy")
    p=profile(cfg,plan.get("deployment_profile"))
    require(p.get("deployment_permitted") is True,"Deployment not authorized")
    require(p.get("destructive") is False,"Destructive deployment needs a separately reviewed path")
    require(plan.get("persistence_preflight") and all(intact(r) for r in plan["persistence_preflight"]),"Persistence/active-work preflight evidence required")
    require(plan.get("verification_passed") is True and plan.get("evidence") and all(Path(x).is_file() for x in plan["evidence"]),"Local tests must pass before delivery")
    require(all(type(plan.get(k)) is bool for k in ("build_required","restart_required")),"Explicit build/restart assessment required")
    require(plan.get("local_test_refs") and all(intact(r) for r in plan["local_test_refs"]),"Local test evidence changed")
    if p["restart_policy"]!="NO_RESTART":require(plan["restart_required"],"Profile requires restart/reload")
    expected=plan["expected_runtime_version"]
    # Validate before executing any commands.
    require(expected.get("build_id") and expected.get("commit_id"),"Expected build identity required")
    required=plan.get("required_runtime_checks",[])
    require(required and "product_case" in required,"Targeted product case required")
    if plan.get("ui_changed"):require("browser" in required,"UI repair requires Browser recheck")
    if plan.get("assistant_changed"):require(set(("browser","real_chat","core_effect","validation","persistence")).issubset(required),"Assistant repair requires real execution chain")
    stages=["preflight"]+(["build"] if plan.get("build_required") else [])+["deploy"]+(["restart"] if plan.get("restart_required") else [])+["retest"]
    commands=p.get("commands",{})
    for stage in stages:
        argv=commands.get(stage)
        require(isinstance(argv,list) and argv and all(isinstance(x,str) and x for x in argv),"Registered argv missing: "+stage)
    directory=Path(directory)/uuid.uuid4().hex;directory.mkdir(parents=True)
    receipt={"repair_id":plan["repair_id"],"status":"IMPLEMENTED_NOT_DEPLOYED","complete":False,"evidence":[],"expected":expected}
    def save():write(directory/"delivery.json",receipt)
    def command(stage):
        argv=[x.replace("{evidence_dir}",str(directory)) for x in commands[stage]]
        log=directory/(stage+".log")
        with log.open("wb") as out:
            result=subprocess.run(argv,cwd=cfg["project"],stdout=out,stderr=subprocess.STDOUT,shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        outcome=directory/(stage+"-result.json");write(outcome,{"argv":argv,"returncode":result.returncode,"at":now()})
        receipt["evidence"].append(ref(outcome))
        if log.stat().st_size:receipt["evidence"].append(ref(log))
        require(result.returncode==0,"Command failed: "+stage)
    try:
        command("preflight")
        # Existing healthy version may be unavailable: preserve that fact, don't invent it.
        try:receipt["runtime_before"]=observe(p,expected)
        except (ValueError,OSError,KeyError) as exc:receipt["runtime_before"]={"unavailable":str(exc)}
        for stage in stages[1:-1]:
            receipt["status"]={"build":"BUILDING","deploy":"DEPLOYING","restart":"RESTARTING"}[stage];save();command(stage)
        receipt["status"]="DEPLOYED_NOT_VERIFIED";save()
        observed=observe(p,expected);receipt["runtime_after"]=observed
        require(observed["version_match"],"RUNTIME_VERSION_MISMATCH")
        require(observed["healthy"],"RUNTIME_HEALTH_FAILED")
        command("retest")
        retest=read(directory/"targeted-runtime-test.json")
        verify_retest(retest,expected,required)
        receipt["evidence"] += [ref(directory/"targeted-runtime-test.json"),*retest["evidence"]]
        after=observe(p,expected);require(after["version_match"] and after["healthy"],"Runtime changed during retest")
        receipt.update(status="CONFIRMED_BY_RUNTIME",complete=True,runtime_after=after)
    except (ValueError,OSError,KeyError) as exc:
        message=str(exc);receipt.update(status="RUNTIME_VERSION_MISMATCH" if "RUNTIME_VERSION_MISMATCH" in message else "DEPLOYMENT_FAILED" if receipt["status"] in ("DEPLOYING","RESTARTING","BUILDING") else "DEPLOYED_NOT_VERIFIED" if receipt["status"]=="DEPLOYED_NOT_VERIFIED" else "IMPLEMENTED_NOT_DEPLOYED",reason=message,rollback_status="NOT_ATTEMPTED")
    save();receipt["receipt_ref"]=ref(directory/"delivery.json")
    return receipt

def verify_delivery(plan,receipt):
    if plan.get("deployment_required") is False:
        require(isinstance(plan.get("delivery_not_applicable"),str) and plan["delivery_not_applicable"].strip(),"Explain why no runtime is affected")
        return
    require(plan.get("deployment_required") is True,"Explicit deployment_required assessment required")
    require(receipt and receipt.get("complete") is True and receipt.get("status")=="CONFIRMED_BY_RUNTIME","IMPLEMENTED_NOT_DEPLOYED: verified delivery required")
    require(receipt.get("expected")==plan.get("expected_runtime_version"),"Delivery belongs to a different repaired build")
    require(intact(receipt["receipt_ref"]) and all(intact(r) for r in receipt["evidence"]),"Runtime delivery evidence changed")
