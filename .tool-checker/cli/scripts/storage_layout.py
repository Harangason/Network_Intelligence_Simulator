"""Owned artifact layout and retention; invoked by the skill, not a background daemon."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, hashlib, json, os, re, shutil, uuid
from contextlib import contextmanager
from tool_check import read, write
DEFAULT_RETENTION = {"archive_after_days": 10, "delete_after_archive_days": 5}

def validate_retention(data):
    if not isinstance(data, dict) or set(data) != set(DEFAULT_RETENTION):
        raise ValueError("Expected archive_after_days and delete_after_archive_days")
    for value in data.values():
        if type(value) is not int or not 1 <= value <= 3650:
            raise ValueError("Retention days must be integers from 1 to 3650")
    return dict(data)

CATEGORIES = ("config", "src", "gates", "tests", "repair", "runs", "docs", "var")
def utc(): return datetime.now(timezone.utc)
def stamp(value):
    value=datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None: raise ValueError("Timezone required")
    return value

def checked(root, relative):
    p=root/relative
    if Path(relative).is_absolute() or not p.resolve().is_relative_to(root.resolve()) or p==root:
        raise ValueError("Path escapes artifact root")
    for item in (p, *p.parents):
        if item==root.parent: break
        if item.is_symlink() or (item.exists() and getattr(item.lstat(),"st_file_attributes",0) & 1024):
            raise ValueError("Links/junctions forbidden")
    return p

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def durable_path(relative):
    parts=Path(relative).parts
    return bool(parts and (parts[0] in {'cli','testcases','config','src','tests'} or
        any(p in {'testcases','selections','profiles'} for p in parts) or
        str(relative).replace('\\','/') in {'Start-Tests.ps1','start.ps1','config.json'}))
def slug(value):
    value=re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower()[:80]
    if not value: raise ValueError("Empty artifact name")
    return value

class Layout:
    def __init__(self, project):
        self.project=Path(project).resolve(strict=True)
        self.root=self.project/".tool-checker"
    @contextmanager
    def lock(self):
        if self.root.is_symlink() or (hasattr(self.root,"is_junction") and self.root.is_junction()):
            raise ValueError("Root link forbidden")
        self.root.mkdir(exist_ok=True)
        path=self.root/".storage.lock"
        fd=os.open(path, os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        try:
            os.close(fd)
            yield
        finally: path.unlink()
    def initialize(self):
        for prefix in ("", "Archiv/"):
            for category in CATEGORIES: checked(self.root,prefix+category).mkdir(parents=True,exist_ok=True)
        for prefix in ("", "Archiv/"):
            for name,body in (("SKILL.md","# Tool Checker workspace\nSee the installed tool-checker skill for execution rules.\n"),
                              ("README.md","# Tool Checker artifacts\nOwned run artifacts only: Retention: config/retention.json; defaults archive after 10 days, delete after 5 days in archive.\n")):
                path=checked(self.root,prefix+name)
                if not path.exists(): path.write_text(body,encoding="utf-8")
        index=checked(self.root,"var/storage-index.json")
        if not index.exists(): write(index,{"version":1,"entries":[]})
    def retention(self):
        path=checked(self.root,"config/retention.json")
        return validate_retention(read(path)) if path.exists() else dict(DEFAULT_RETENTION)
    def save_retention(self,data):
        data=validate_retention(data)
        path=checked(self.root,"config/retention.json")
        path.parent.mkdir(parents=True,exist_ok=True)
        write(path,data)
        return self.retention()
    def busy(self):
        # Legacy and new runtime locks both protect migration and retention.
        for base in (self.project/".tool-checker",self.root/"var"):
            for folder in (base/"locks",base/"state"):
                if folder.exists() and any(p.name in ("campaign.json","mutation.json",".state.lock") for p in folder.rglob("*")):
                    return True
        return False
    def migrate(self,plan):
        self.initialize()
        if self.busy(): return {"blocked":"Active project locks; migration deferred"}
        if plan.get("references_checked") is not True:
            raise ValueError("Review references and terminal run ownership before migration")
        index=read(self.root/"var/storage-index.json")
        planned=[]
        sources=set();destinations=set()
        for entry in plan["items"]:
            source=checked(self.project,entry["source"])
            if not (source.is_relative_to(self.project/"tool-checker") or source.is_relative_to(self.root)):
                raise ValueError("Import restricted to owned Tool Checker workspace")
            owner = self.root if source.is_relative_to(self.root) else self.project/"tool-checker"
            relative = source.relative_to(owner)
            if durable_path(relative): raise ValueError('Active scripts/configuration are not historical run artifacts')
            if relative.parts[0] in {"Archiv", "var", "state", "locks"} or relative.as_posix() in {"SKILL.md", "README.md"}:
                raise ValueError("Control and archive files cannot be imported")
            if any(e.get("source")==entry["source"] and not e.get("deleted_at") for e in index["entries"]):
                raise ValueError("Source already registered; inspect interrupted migration")
            if not source.is_file() or sha(source)!=entry["sha256"]:
                raise ValueError("Source missing/changed")
            category=entry["category"]
            if category not in CATEGORIES or category=="var":
                raise ValueError("Runtime state migration requires a separate reviewed reference migration")
            if entry.get("terminal") is not True or not entry.get("run_id"):
                raise ValueError("Terminal run ownership required")
            completed=stamp(entry["completed_at"])
            name=stamp(entry.get("started_at",entry["completed_at"])).strftime("%Y%m%d")+"_src_"+slug(entry["markdown"])+"_"+slug(entry["test_case"])
            name+="_"+slug(source.stem)+"_"+uuid.uuid4().hex[:10]+source.suffix
            relative=category+"/"+name; target=checked(self.root,relative)
            if target.exists() or source in sources or target in destinations: raise ValueError("Collision")
            sources.add(source);destinations.add(target)
            planned.append((source,target,dict(entry,path=relative,archived_at=None)))
        # One file per commit, recoverable after interruption: duplicate copies are harmless.
        for source,target,entry in planned:
            shutil.copy2(source,target)
            if sha(target)!=entry["sha256"]: raise ValueError("Copy verification failed")
            index["entries"].append(entry); write(self.root/"var/storage-index.json",index)
            source.unlink()
        return {"migrated":len(planned)}
    def maintain(self,at=None):
        self.initialize()
        if self.busy(): return {"blocked":"Active project locks; retention deferred"}
        policy=self.retention()
        at=at or utc(); index=read(self.root/"var/storage-index.json")
        result={"archived":0,"deleted":0,"protected":0}
        for entry in index["entries"]:
            if entry.get("deleted_at"): continue
            parts=Path(entry["path"]).parts
            if durable_path(entry["path"]) or entry.get("durable"):
                result["protected"]+=1; continue
            p=checked(self.root,entry["path"])
            if not p.is_file() or sha(p)!=entry["sha256"] or entry.get("pinned"):
                result["protected"]+=1; continue
            if entry.get("archived_at"):
                if at-stamp(entry["archived_at"])>timedelta(days=policy["delete_after_archive_days"]):
                    if not entry["path"].startswith("Archiv/"): raise ValueError("Deletion outside archive denied")
                    p.unlink();entry["deleted_at"]=at.isoformat();result["deleted"]+=1
            elif at-stamp(entry["completed_at"])>timedelta(days=policy["archive_after_days"]):
                relative="Archiv/"+entry["path"]
                dest=checked(self.root,relative)
                if dest.exists(): raise ValueError("Archive collision")
                shutil.copy2(p,dest)
                if sha(dest)!=entry["sha256"]: raise ValueError("Archive copy changed")
                old=p;entry["path"]=relative;entry["archived_at"]=at.isoformat()
                write(self.root/"var/storage-index.json",index)
                old.unlink();result["archived"]+=1
            write(self.root/"var/storage-index.json",index)
        return result

def main():
    p=argparse.ArgumentParser();p.add_argument("--project",required=True)
    p.add_argument("action",choices=["init","migrate","maintain"]);p.add_argument("--plan")
    a=p.parse_args();obj=Layout(a.project)
    with obj.lock():
        result=obj.initialize() if a.action=="init" else obj.migrate(read(a.plan)) if a.action=="migrate" else obj.maintain()
    print(json.dumps(result or {"root":str(obj.root)},ensure_ascii=False))
if __name__=="__main__":main()
