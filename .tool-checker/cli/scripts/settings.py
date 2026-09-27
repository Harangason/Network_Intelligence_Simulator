"""Render a settings panel or save project retention; never run retention here."""
import argparse
import json
from pathlib import Path
from storage_layout import Layout

def panel(project):
    layout=Layout(project)
    data={"project":str(layout.project),"retention":layout.retention()}
    payload=json.dumps(data,ensure_ascii=False).replace("<","\\u003c").replace("&","\\u0026").replace("\u2028","\\u2028").replace("\u2029","\\u2029")
    template=Path(__file__).resolve().parents[1]/"assets/settings.html"
    return template.read_text(encoding="utf-8").replace("__TOOL_CHECKER_SETTINGS__",payload)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("panel","save","show"))
    parser.add_argument("--project",required=True)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--archive-days",type=int)
    parser.add_argument("--delete-days",type=int)
    args=parser.parse_args()
    layout=Layout(args.project)
    if args.action=="panel":
        if not args.output:parser.error("--output required")
        args.output.write_text(panel(args.project),encoding="utf-8")
        print(args.output.resolve())
    elif args.action=="save":
        with layout.lock():
            print(json.dumps(layout.save_retention({"archive_after_days":args.archive_days,"delete_after_archive_days":args.delete_days})))
    else:print(json.dumps(layout.retention()))

if __name__=="__main__":main()
