"""Explicit opt-in one-turn synthetic protocol probe; never run during verify."""
import argparse
import json
from pathlib import Path
import tempfile
import time
from codex_repair import CodexAppServer, protected_json

def probe(executable, evidence, allow_model_turn=False):
    observations = []
    with tempfile.TemporaryDirectory(prefix='toolchecker-codex-protocol-', ignore_cleanup_errors=True) as isolated:
        c=CodexAppServer(executable, isolated, log=observations.append)
        record={'handshake':False,'real_server_request':False,'response_sent':False,'model_turn':False}
        try:
            c.initialize(); record['handshake']=True
            if allow_model_turn:
                record['model_turn']=True
                c.thread_id=c.call('thread/start', {'cwd':isolated,'ephemeral':True,
                    'sandbox':'read-only','approvalPolicy':'on-request','approvalsReviewer':'user'})['thread']['id']
                turn=c.call('turn/start', {'threadId':c.thread_id,'summary':'none','input':[{
                    'type':'text','text_elements':[], 'text':
                    'Synthetic protocol acceptance test only. Do not inspect files or use network. '
                    'Use the command tool exactly once to request elevated permission (sandbox_permissions=require_escalated) '
                    'for the harmless command echo toolchecker_protocol_fixture, with the approval question: '
                    'May this synthetic echo run? The user will decline. After decline stop, no retry. '
                    'If the command tool cannot request approval, say unavailable and stop.'}]})
                c.turn_id=turn['turn']['id']
                deadline=time.monotonic()+60
                while time.monotonic()<deadline and c.turn_result is None:
                    event=c.receive()
                    if event and event.get('method') == 'item/completed':
                        item=event.get('params',{}).get('item',{})
                        if item.get('type') == 'commandExecution':
                            record['command_status']=item.get('status')
                    if c.pending:
                        req=next(iter(c.pending.values()))
                        record['real_server_request']=True
                        record['request_method']=req['method']
                        if req['method'].endswith('requestApproval'):
                            c.answer(req['id'], {'decision':'decline'}); record['response_sent']=True
                        else:
                            c.abort(); record['unsupported_probe_request']=True; break
                    if c.state=='DISCONNECTED': break
                record['turn_completed']=c.turn_result is not None
                if c.turn_result is None: c.abort()
        except Exception as error:
            record['error_type']=type(error).__name__
        finally: c.close()
        record['events']=observations
        protected_json(evidence, record)
        return record

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--executable',required=True)
    p.add_argument('--evidence',required=True); p.add_argument('--allow-model-turn',action='store_true')
    a=p.parse_args()
    r=probe(a.executable,a.evidence,a.allow_model_turn)
    print(json.dumps({k:v for k,v in r.items() if k!='events'}))
