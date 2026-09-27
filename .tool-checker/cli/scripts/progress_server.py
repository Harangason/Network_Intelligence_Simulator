"""Local, token-protected dashboard; polling never calls an LLM."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit
from tool_check import read, write

def server_for(jobs, port=18764, token=None):
    token = token or secrets.token_urlsafe(32)
    controls = threading.Lock()
    asset = Path(__file__).resolve().parent.parent/"assets"/"progress.html"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self, status, data, content_type="application/json"):
            body = json.dumps(data,ensure_ascii=False).encode() if content_type=="application/json" else data
            self.send_response(status)
            self.send_header("Content-Type",content_type)
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.end_headers()
            self.wfile.write(body)
        def authorized(self):
            return secrets.compare_digest(self.headers.get("Authorization",""),"Bearer "+token)
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=="/":
                return self.send(200,asset.read_bytes(),"text/html; charset=utf-8")
            if not self.authorized():
                return self.send(401,{"error":"Local dashboard token required"})
            parts=path.strip("/").split("/")
            try:
                if parts==["tool-check","jobs"]:
                    return self.send(200,jobs.list())
                if len(parts)>=3 and parts[:2]==["tool-check","jobs"]:
                    job_id=parts[2]
                    if len(parts)==3: return self.send(200,jobs.view(job_id))
                    if parts[3:]==["details"]: return self.send(200,jobs.details(job_id))
                    if len(parts)==5 and parts[3]=="evidence":
                        job=jobs.load(job_id); directory=jobs.tc.run_dir(job["run_id"],job["task_id"])
                        result=read(directory/"result.json")
                        entry=next(x for x in result["evidence"] if x["id"]==parts[4])
                        target=(directory/entry["path"]).resolve()
                        if not target.is_relative_to(directory.resolve()): raise ValueError("Invalid evidence path")
                        from tool_check import file_hash
                        if file_hash(target)!=entry["sha256"]: raise ValueError("Evidence integrity error")
                        return self.send(200,target.read_bytes(),mimetypes.guess_type(target)[0] or "application/octet-stream")
                if len(parts)==3 and parts[:2]==["tool-check","batches"]:
                    return self.send(200,jobs.batch(parts[2]))
                self.send(404,{"error":"Not found"})
            except (OSError,ValueError,KeyError,StopIteration) as error:
                self.send(400,{"error":str(error)})
        def do_POST(self):
            if not self.authorized():
                return self.send(401,{"error":"Local dashboard token required"})
            origin=self.headers.get("Origin")
            allowed={f"http://127.0.0.1:{self.server.server_port}",f"http://localhost:{self.server.server_port}"}
            if origin and origin not in allowed:
                return self.send(403,{"error":"Cross-origin control denied"})
            try:
                size=int(self.headers.get("Content-Length","0"))
                if not 0<=size<=8192: raise ValueError("Request too large")
                payload=json.loads(self.rfile.read(size) or b"{}")
                parts=urlsplit(self.path).path.strip("/").split("/")
                if len(parts)!=4 or parts[:2]!=["tool-check","jobs"]: return self.send(404,{"error":"Not found"})
                with controls:
                    if parts[3]=="start": result=jobs.launch(parts[2])
                    elif parts[3]=="cancel": result=jobs.cancel(parts[2])
                    elif parts[3]=="answer": result=jobs.answer(parts[2],payload["step_id"],payload["choice"])
                    else: return self.send(404,{"error":"Not found"})
                self.send(200,result)
            except (OSError,ValueError,KeyError,TypeError) as error:
                self.send(400,{"error":str(error)})
    httpd=ThreadingHTTPServer(("127.0.0.1",port),Handler)
    return httpd,token

def serve(jobs,port=18764):
    httpd,token=server_for(jobs,port)
    url=f"http://127.0.0.1:{httpd.server_port}/#token={token}"
    write(jobs.tc.root/"runtime"/"dashboard.json",{"url":url,"port":httpd.server_port})
    print(json.dumps({"url":url,"host":"127.0.0.1","status":"READY"}),flush=True)
    try: httpd.serve_forever()
    finally: httpd.server_close()
