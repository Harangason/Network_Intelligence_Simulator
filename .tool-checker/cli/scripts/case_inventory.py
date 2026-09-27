"""Durable, revision-bound native case entries. Never executes product actions."""
from pathlib import Path
import json
import shutil
import sys
import re
from tool_check import read, write, digest, file_hash, ident
from progress_model import plan_for

FORMAT = 1

def artifacts(checker):
    return Path(checker.cfg()["project"]).resolve() / ".tool-checker"

def revision_for(case, manifest):
    common = {k:manifest.get(k) for k in ("global_rules","architecture_rules","rule_files","required_skills","required_tools","required_views","required_outputs")}
    return digest({"format":FORMAT,"contract":functional(case),"common":common})

def safe(root, relative):
    root = Path(root).resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError("Durable path escapes owner")
    for item in (path, *path.parents):
        if item == root.parent: break
        if item.is_symlink() or (item.exists() and getattr(item.lstat(), "st_file_attributes", 0) & 1024):
            raise ValueError("Durable links/junctions forbidden")
    return path

def functional(case):
    return {k:v for k,v in case.items() if k not in {"status", "last_run", "contract_hash"}}

def adapter_path_blockers(argv, project):
    """Check executable and interpreter script without running a configured command."""
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a for a in argv):
        return ["Adapter argv must be a nonempty string array"]
    root = Path(project).resolve()
    def existing(value):
        path = Path(value)
        return (path if path.is_absolute() else root / path).is_file()
    executable = argv[0]
    qualified = Path(executable).is_absolute() or '/' in executable or '\\' in executable
    if (qualified and not existing(executable)) or (not qualified and not shutil.which(executable)):
        return ["Adapter executable missing: " + executable]
    interpreter = Path(executable).stem.lower()
    arguments = argv[1:]
    script = None
    if interpreter.startswith('python') or interpreter in ('py', 'node', 'nodejs'):
        index = 0
        while index < len(arguments):
            value = arguments[index]
            if value in ('-c', '-m', '-e', '--eval', '-p', '--print'):
                break  # Inline programs/modules are not filesystem script paths.
            if value == '--':
                script = arguments[index + 1] if index + 1 < len(arguments) else None
                break
            if value.startswith('-'):
                index += 2 if value in ('-W', '-X', '--require', '-r', '--loader', '--import') else 1
                continue
            script = value
            break
    elif interpreter in ('powershell', 'pwsh'):
        for index, value in enumerate(arguments):
            if value.lower() in ('-command', '-encodedcommand', '-c', '-ec'):
                break
            if value.lower() in ('-file', '-f'):
                script = arguments[index + 1] if index + 1 < len(arguments) else None
                break
    if script and not existing(script):
        return ["Adapter script missing: " + script]
    return []


def readiness(case, cfg):
    blockers = __import__("plan_registry").parameter_blockers(case,cfg)
    if not case.get('execution_plan'):
        blockers.append('Ausführungsplan fehlt. Fachliche Schritte und Originalkriterien implementieren und lokal registrieren: '
            'python .tool-checker/cli/scripts/plan_registry.py --state <State> --task <Task> register '
            +case['test_id']+' --plan <geprüfte-Plan-Datei.json>')
        if case.get('browser_required'):
            blockers.append('Browser adapter required: bind a reviewed browser runner and real UI assertions before execution.')
        return blockers
    try: plan, _ = plan_for(case)
    except (ValueError, TypeError) as error:
        return [str(error)]
    try: policy = __import__('plan_registry').effective_llm_policy(case,cfg)
    except ValueError as error: return blockers + [str(error)]
    for step in plan:
        if step.get("kind") == "adapter":
            adapter = cfg.get("adapters", {}).get(step["adapter"])
            if not adapter: blockers.append("Adapter not configured: " + step["adapter"])
            elif not isinstance(adapter.get("argv"), list) or not adapter["argv"]:
                blockers.append("Adapter argv missing: " + step["adapter"])
            else:
                blockers.extend(adapter_path_blockers(adapter["argv"], cfg.get("project", ".")))
            if adapter and (type(adapter.get("mutating")) is not bool or (adapter["mutating"] and not case["mutating"])):
                blockers.append("Adapter mutation scope conflicts: " + step["adapter"])
            if adapter and policy == "DISABLED" and adapter.get("uses_llm") is not False:
                blockers.append("DISABLED requires non-LLM adapter: " + step["adapter"])
        if step.get("required_parameters"):
            args = step.get("arguments", {})
            missing = [key for key in step["required_parameters"] if key not in args or args[key] in (None, "")]
            if missing: blockers.append("Missing parameters: " + ", ".join(missing))
    return blockers

def group_for(case):
    if case.get('group'):return case['group']
    tags=[tag for tag in case.get('tags',[]) if tag.lower() not in ('eip','positive','negative','browser','read','write')]
    for family in ('scenario','automotive','quality','board','editor','mcp','agent','assistant','assistant-system','regression'):
        if family in tags:return family
    return re.split(r'\d|[-_]',case['test_id'],maxsplit=1)[0] or 'Tests'

def entry_text(task, test):
    return ('#!/usr/bin/env python3\n"""Revision-bound Tool Checker entry; uses native gates and Jobs."""\n'
            'from pathlib import Path\nimport sys\n'
            'sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "cli" / "scripts"))\n'
            'from standard_cli import case_entry\n'
            f'if __name__ == "__main__": raise SystemExit(case_entry({task!r}, {test!r}, Path(__file__).parent))\n')

def archived_candidates(root, task, test, revision):
    matches=[]
    for index_path in (root/'Archiv').rglob('index.json') if (root/'Archiv').exists() else []:
        try:
            index=read(index_path)
            if index.get('task_id')!=task:continue
            record=index.get('cases',{}).get(test,{})
            if record.get('revision')!=revision or set(record.get('files',{})) != {'run.py','contract.json','binding.json'}:continue
            directory=index_path.parent/test
            directory=safe(root,directory.relative_to(root))
            if all((directory/name).is_file() and file_hash(directory/name)==sha for name,sha in record['files'].items()):
                matches.append((directory,record))
        except (ValueError,OSError,TypeError):continue
    return matches

def materialize(checker, task=None):
    """All registered cases before any selection; hashes/mtimes unchanged on cache hit."""
    installation=install(checker)
    task = ident(task or checker.manifest()["task_id"])
    manifest = checker.manifest(task)
    root = artifacts(checker)
    project_settings=root/'config/project-cli.json'
    aliases=read(project_settings).get('group_aliases',{}) if project_settings.exists() else {}
    folder = safe(root, "testcases/" + task)
    index_path = folder / "index.json"
    old = read(index_path) if index_path.exists() else {"cases": {}}
    index = {"format":FORMAT, "task_id":task, "cases":dict(old["cases"])}
    conflicts = []
    changed = []
    for test in manifest["test_case_ids"]:
        ident(test)
        case = read(checker.task(task)/"test_cases"/(test+".json"))
        contract = functional(case)
        revision = revision_for(case,manifest)
        case_dir = safe(root, "testcases/" + task + "/" + test)
        record = old["cases"].get(test)
        if not record and not case_dir.exists():
            archived=archived_candidates(root,task,test,revision)
            if len(archived)>1:
                conflicts.append({'test_id':test,'reason':'Ambiguous archived ID/revision; originals preserved','paths':[str(p) for p,_ in archived]})
                continue
            if archived:
                source,record=archived[0];case_dir.mkdir(parents=True)
                for name in record['files']:shutil.copy2(source/name,case_dir/name)
        if not record and case_dir.exists() and any(case_dir.iterdir()):
            conflicts.append({"test_id":test,"path":str(case_dir),"reason":"Unowned/interrupted files preserved; explicit adoption required"})
            continue
        if record:
            for name, expected in record.get("files", {}).items():
                path = case_dir / name
                if not path.is_file() or file_hash(path) != expected:
                    conflicts.append({"test_id":test, "path":str(path), "reason":"Manual edit or missing durable file preserved"})
            if any(c["test_id"] == test for c in conflicts): continue
        if not record or record["revision"] != revision:
            if record:
                history = safe(root, "testcases/"+task+"/history/"+test+"/"+record["revision"])
                history.mkdir(parents=True, exist_ok=True)
                for name in record["files"]:
                    target = history/name
                    if target.exists() and file_hash(target) != record["files"][name]:
                        raise ValueError("Historical revision collision")
                    if not target.exists(): shutil.copy2(case_dir/name, target)
            case_dir.mkdir(parents=True, exist_ok=True)
            write(case_dir/"contract.json", contract)
            (case_dir/"run.py").write_text(entry_text(task,test), encoding="utf-8")
            write(case_dir/"binding.json", {"format":FORMAT,"task_id":task,"test_id":test,"revision":revision,
                "contract_hash":case["contract_hash"],"native_runner":"tool_jobs.Jobs.submit",
                "criteria":{key:case.get(key,[]) for key in ("preconditions","required_actions","completion_criteria","failure_conditions")}})
            record = {"revision":revision,"files":{name:file_hash(case_dir/name) for name in ("contract.json","run.py","binding.json")}}
            changed.append(test)
        try:
            resolved=__import__("plan_registry").resolve_case(checker,task,case)
            plan_registered=bool(resolved.get("execution_plan"))
            plan_blockers=readiness(resolved,checker.cfg())
        except ValueError as error:
            plan_registered=False;plan_blockers=[str(error)]
        group=group_for(case)
        index["cases"][test] = {**record,"active":True,"title":case["title"],"group":aliases.get(group,group),
            "browser_required":case["browser_required"],"mutating":case["mutating"],"registered_plan":plan_registered,"blockers":plan_blockers,"path":str(case_dir/"run.py")}
    for test in set(index["cases"]) - set(manifest["test_case_ids"]):
        index["cases"][test] = {**index["cases"][test],"active":False,"superseded":True}
    if not index_path.exists() or read(index_path) != index: write(index_path,index)
    active = [v for v in index["cases"].values() if v["active"]]
    report = {"task_id":task,"status":"INCOMPLETE" if installation['conflicts'] or conflicts or any(v["blockers"] for v in active) else "IMPLEMENTED",
        "installation_conflicts":installation['conflicts'],
        "total":len(manifest["test_case_ids"]),"entries":len(active),"registered_plans":sum(v.get("registered_plan",False) for v in active),"implemented":sum(not v["blockers"] for v in active),
        "changed":changed,"conflicts":conflicts,"blocked":{k:v["blockers"] for k,v in index["cases"].items() if v["active"] and v["blockers"]}}
    report_path = folder/"materialization.json"
    if not report_path.exists() or read(report_path) != report: write(report_path,report)
    return report

def binding(checker, task, test):
    record = read(safe(artifacts(checker),"testcases/"+ident(task)+"/index.json"))["cases"][ident(test)]
    directory = Path(record["path"]).parent
    if not record["active"]: raise ValueError("Superseded case")
    for name, expected in record["files"].items():
        if file_hash(directory/name) != expected: raise ValueError("Durable manual edit conflict: "+test)
    current = read(checker.task(task)/"test_cases"/(test+".json"))
    if revision_for(current,checker.manifest(task)) != record["revision"]:
        raise ValueError("Durable revision outdated: "+test)
    resolved=__import__("plan_registry").resolve_case(checker,task,current)
    return {"plan_binding":resolved.get("plan_binding"),"revision":record["revision"],"entry":record["path"],"entry_sha256":record["files"]["run.py"],"contract_sha256":record["files"]["contract.json"]}

def install(checker, reviewed=False):
    """Copy bundled native code; preserve user edits and previous revisions."""
    source = Path(__file__).parent
    root=artifacts(checker)
    destination = safe(root,"cli/scripts")
    destination.mkdir(parents=True, exist_ok=True)
    ownership = root/"cli"/"installed.json"
    old = read(ownership) if ownership.exists() else {"files":{}}
    files = {}; conflicts = []
    inputs = [(p,destination/p.name) for p in source.glob("*.py")]
    for category in ('assets','config','adapters'):
        resource_root=source.parent/category
        if resource_root.exists():
            for resource in sorted(resource_root.rglob('*')):
                if resource.is_file() and '__pycache__' not in resource.parts:
                    if resource.is_symlink():raise ValueError('Bundled resource link forbidden')
                    inputs.append((resource,root/'cli'/category/resource.relative_to(resource_root)))
    inputs += [(source.parent/"assets"/"Start-Tests.ps1",root/"Start-Tests.ps1")]
    for original, target in inputs:
        relative = target.relative_to(root).as_posix()
        target = safe(root,relative)
        target.parent.mkdir(parents=True,exist_ok=True)
        sha = file_hash(original)
        if target.exists() and file_hash(target) != sha:
            if old["files"].get(relative) != file_hash(target):
                if not reviewed or relative != 'Start-Tests.ps1':
                    conflicts.append(relative); continue
                backup=safe(root,'cli/history/'+file_hash(target)+'/'+target.name)
                backup.parent.mkdir(parents=True,exist_ok=True)
                if not backup.exists():shutil.copy2(target,backup)
            history = safe(root,"cli/history/"+file_hash(target)+"/"+target.name)
            history.parent.mkdir(parents=True,exist_ok=True)
            if not history.exists(): shutil.copy2(target,history)
        if not target.exists() or file_hash(target) != sha: shutil.copy2(original,target)
        files[relative] = sha
    settings=root/"cli"/"project.json"
    setting={"state":str(checker.root),"project":str(Path(checker.cfg()["project"]).resolve())}
    if not settings.exists(): write(settings,setting)
    elif read(settings)!=setting: conflicts.append("cli/project.json: existing state binding preserved")
    result = {"files":files,"conflicts":conflicts}
    if not ownership.exists() or read(ownership) != result: write(ownership,result)
    return result
