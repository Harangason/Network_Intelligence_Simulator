"""Read-only stream ownership reproduction; fake bounded handler, no model/SQL/inference."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,threading
from pathlib import Path
from datetime import datetime,timezone
import sys
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from flask import Flask
from backend.nis.agent.tools import api
from backend.nis.agent.api.tool_contract import ToolResult
started=threading.Event();release=threading.Event();finished=threading.Event();after_disconnect=threading.Event()
original_execute,original_executor=api.execute,api._executor
owned=ThreadPoolExecutor(max_workers=1)
def execute(authority,name,permission,arguments,handler):
 return handler(arguments)
def handler(arguments):
 started.set()
 try:
  if not release.wait(5):raise RuntimeError('diagnostic release missing')
  after_disconnect.set()
  return ToolResult(data={'fixture':'completed_after_browser_left'})
 finally:finished.set()
app=Flask('document-stream-lifecycle-reproduction')
app.post('/document')(lambda:api._local_document_response('interpret_project_document',handler,'initial progress'))
api.execute,api._executor=execute,owned
try:
 response=app.test_client().post('/document',json={'source_request_id':'diagnostic'},headers={'Accept':'application/x-ndjson','X-Project-ID':'diagnostic-document-stream'},buffered=False)
 assert response.status_code==200 and started.wait(3)
 response.close()
 release.set()
 assert finished.wait(3)
 result={'at_utc':datetime.now(timezone.utc).isoformat(),'browser_stream_closed':True,'worker_continued_to_next_stage':after_disconnect.is_set(),'root_cause_reproduced':after_disconnect.is_set(),'scope':__doc__,'api_file_sha256':hashlib.sha256((ROOT/'backend/nis/agent/tools/api.py').read_bytes()).hexdigest(),'canonical_writes':False,'production_mutation':False,'model_calls':0,'sql_calls':0}
 print(json.dumps(result),flush=True)
 Path(__file__).with_name('disconnect-reproduction.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
finally:
 release.set();owned.shutdown(wait=True);api.execute,api._executor=original_execute,original_executor
