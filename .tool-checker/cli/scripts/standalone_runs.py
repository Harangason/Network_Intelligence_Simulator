"""Sequential independent runs over the native Jobs and Core evaluator."""
from pathlib import Path
import uuid
import re
from tool_check import digest, file_hash, now, write, read
from tool_jobs import Jobs
from case_inventory import artifacts


def message(code, case_id, text, next_action, scope='case'):
    text=re.sub(r'^(?:(?:BLOCKED|FAIL(?:ED)?|ABORTED|ERROR):\s*)+', '', str(text)).strip()
    return dict(code=code, scope=scope, case_id=case_id, message=text, next_action=next_action)


def deduplicate(rows):
    return list({(r['code'],r['scope'],r['case_id']):r for r in rows}.values())


def run_rounds(cli, items, inputs, rounds=1, behavior='continue', mode='verify', show_progress=True):
    if inputs is not None and not isinstance(inputs,dict): raise ValueError('Inputs müssen eine ID-Abbildung sein')
    if not items: raise ValueError('Keine Testfälle ausgewählt')
    if type(rounds) is not int or rounds < 1: raise ValueError('Positive round count required')
    if behavior not in ('continue','stop','pause') or mode not in ('verify','repair'): raise ValueError('Unknown run behavior')
    tc=cli.checker; root=artifacts(tc)/'runs/standalone'; root.mkdir(parents=True,exist_ok=True)
    bundle={'session_id':'session-'+uuid.uuid4().hex,'execution_scope':'standalone','task_id':cli.task,
            'messages':[],'created_at':now(),'rounds_requested':rounds,'mode':mode,'error_behavior':behavior,'rounds':[]}
    session_path=root/(bundle['session_id']+'.json')
    def persist(): write(session_path,bundle)
    jobs=Jobs(tc.root)
    def execute(case, retest=False):
        automatic=inputs is None
        saved={} if automatic else inputs.get(case['test_id'],{})
        spec=cli.prepare_case_inputs(case,n,retest) if automatic else saved
        if not isinstance(spec,dict): raise ValueError('Ungültige Inputs für '+case['test_id'])
        if not automatic and case.get('mutating') and (n>1 or retest):
            spec=saved.get('repair_retest') if retest else saved.get('round_inputs',{}).get(str(n))
            if not isinstance(spec,dict):raise ValueError('Mutation benötigt neue laufbezogene Preflight-/Baseline-Belege')
            if not spec.get('preflight'):raise ValueError('Frische Mutationspreflight-Datei fehlt')
            boundary=repair_started_at if retest else bundle['rounds'][-2]['finished_at']
            if read(spec['preflight']).get('checked_at','')<boundary:
                raise ValueError('Mutationspreflight wurde vor dem vorherigen Prüf-/Reparaturschritt erstellt')
        if not spec.get('preflight'): raise ValueError('Frische Preflight-Datei fehlt')
        cli.prevalidate([case],{case['test_id']:spec},execution_scope='standalone')
        submitted=jobs.submit(cli.task,case['test_id'],spec['preflight'],spec.get('baseline'),queued=True,execution_scope='standalone')
        old_emit=jobs.emit
        def emit(job,kind,step=None):
            update=old_emit(job,kind,step)
            value=job.get('percentage'); label='unbekannt' if value is None else f'{value:g}%'
            filled=0 if value is None else int(value/5)
            title=' '.join(case['title'].split())[:60]
            if show_progress:cli.output('\r'+case['test_id']+' '+title+' ['+'#'*filled+'-'*(20-filled)+'] '+label,end='',flush=True)
            if kind=='WAITING_FOR_USER':
                cli.output('')
                decision=job['decision']
                while True:
                    cli.output(decision['question']+' — '+', '.join(decision['options'])+' / ABORT')
                    try:choice=cli.input('> ').strip()
                    except (EOFError,StopIteration):jobs.cancel(job['job_id']);break
                    if choice=='ABORT':jobs.cancel(job['job_id']);break
                    if choice in decision['options']:jobs.answer(job['job_id'],decision['step_id'],choice);break
                    cli.output('Gültige ausdrückliche Antwort erforderlich')
            return update
        jobs.emit=emit
        try:jobs.work(submitted['job_id'])
        finally:
            jobs.emit=old_emit
            if show_progress:cli.output('')
        job=jobs.load(submitted['job_id'])
        return {'case_id':case['test_id'],'job_id':job['job_id'],'run_id':job['run_id'],
                'status':{'COMPLETE':'PASS','FAILED':'FAIL','CANCELLED':'ABORTED'}.get(job['status'],job['status']),
                'percentage':job.get('percentage'),'result_ref':job.get('result_ref'),
                'messages':[] if job['status']=='COMPLETE' else [message('RUNNER_'+job['status'],case['test_id'],job.get('message',''), 'Details prüfen und Voraussetzungen korrigieren')]}
    halted=False
    for n in range(1,rounds+1):
        row={'round_id':'round-'+uuid.uuid4().hex,'round':n,'started_at':now(),'source_hash':tc.manifest(cli.task)['source_hash'],
             'config_hash':digest(tc.cfg()),'code_hash':digest({p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py')}),
             'test_ids':[c['test_id'] for c in items],'cases':[],'status':'RUNNING'}
        bundle['rounds'].append(row);persist()
        for case in items:
            try:result=execute(case)
            except KeyboardInterrupt:
                result={'case_id':case['test_id'],'status':'ABORTED','percentage':None,'messages':[]};halted=True
            except Exception as error:
                missing_plan='requires a reviewed execution_plan' in str(error)
                text='Ausführungsplan fehlt.' if missing_plan else str(error)
                action=('Fachliche Schritte und Originalkriterien implementieren; lokal registrieren mit python '
                    '.tool-checker/cli/scripts/plan_registry.py --state <State> --task '+cli.task+' register '
                    +case['test_id']+' --plan <geprüfte-Plan-Datei.json>') if missing_plan else 'Plan und frische Voraussetzungen in Details prüfen'
                result={'case_id':case['test_id'],'status':'BLOCKED','percentage':None,'technical_detail':str(error),
                    'messages':[message('PLAN_MISSING' if missing_plan else 'CASE_NOT_EXECUTABLE',case['test_id'],text,action)]}
            result['messages']=deduplicate(result.get('messages',[]))
            row['cases'].append(result);persist()
            if show_progress:
                for problem in result['messages']:
                    cli.output(case['test_id']+' '+result['status']+': '+problem['message'])
                    if problem.get('next_action'): cli.output('Nächster Schritt: '+problem['next_action'])
            if mode=='repair' and result['status']=='FAIL':
                from codex_repair import repair_case
                repair_started_at=now()
                result['repair']=repair_case(tc,cli.task,case,result,cli.input,cli.output,retest=lambda c:execute(c,retest=True))
                persist()
                if result['repair'].get('status') in ('BLOCKED','INPUT_REQUIRED'):
                    while True:
                        cli.output('Reparatur wartet: '+result['repair'].get('message','Details prüfen')+' — v nur Befundung fortsetzen / a Abbrechen')
                        try:answer=cli.input('> ').strip().lower()
                        except (EOFError,StopIteration):answer='input_required'
                        if answer=='v':mode='verify';bundle['mode_changes']=bundle.get('mode_changes',[])+[{'at':now(),'mode':'verify','explicit':True}];break
                        if answer in ('a','input_required'):halted=True;break
                        cli.output('Gültige ausdrückliche Antwort erforderlich')
                    persist()
            if result['status']!='PASS':
                if behavior=='stop':halted=True
                elif behavior=='pause' and not halted:
                    row['status']='WAITING_FOR_USER';persist()
                    while True:
                        cli.output(case['test_id']+' '+result['status']+' — c Fortsetzen / a Abbrechen')
                        try:answer=cli.input('> ').strip().lower()
                        except (EOFError,StopIteration):answer='input_required'
                        if answer=='c':row['status']='RUNNING';break
                        if answer=='a':halted=True;break
                        if answer=='input_required':row['status']='INPUT_REQUIRED';halted=True;break
                        cli.output('Gültige ausdrückliche Antwort erforderlich')
            if halted:break
        started=any(c.get('run_id') for c in row['cases'])
        row['status']=('NOT_STARTED' if not started else 'ABORTED' if halted else 'PASS' if len(row['cases'])==len(items) and all(c['status']=='PASS' for c in row['cases']) else 'INCOMPLETE') if row['status']!='INPUT_REQUIRED' else 'INPUT_REQUIRED'
        row['finished_at']=now();row['report_path']=str(root/(row['round_id']+'.json'));write(row['report_path'],row);persist()
        if halted:break
    bundle['status']='NOT_STARTED' if not any(c.get('run_id') for r in bundle['rounds'] for c in r['cases']) else 'PASS' if len(bundle['rounds'])==rounds and all(r['status']=='PASS' for r in bundle['rounds']) else 'INCOMPLETE'
    bundle['finished_at']=now();bundle['report_path']=str(session_path);persist();return bundle
