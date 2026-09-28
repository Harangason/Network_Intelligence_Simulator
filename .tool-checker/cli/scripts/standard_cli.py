"""Project-independent menu facade over the existing Checker, Jobs and progress model."""
from __future__ import annotations
import shutil
import argparse
import difflib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import unicodedata
import uuid
from tool_check import Checker, read, write, ident, digest, now
from tool_jobs import Jobs
from progress_model import TERMINAL, plan_for
from case_inventory import materialize, install, binding, safe, artifacts

def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(text).casefold()) if not unicodedata.combining(c))

def fuzzy(cases, query):
    query = normalized(query).strip()
    if not query: return list(cases)
    scored = []
    for case in cases:
        words = normalized(' '.join(str(case.get(k,'')) for k in ('test_id','title','group','input','tags'))).split()
        text = ' '.join(words)
        score = 1 if query in text else max((difflib.SequenceMatcher(None,query,word).ratio() for word in words),default=0)
        if score >= .65: scored.append((score,case))
    return [c for _,c in sorted(scored,key=lambda x:-x[0])]

def render_message(status, row):
    from standalone_runs import message
    clean=message(row['code'],row.get('case_id'),row['message'],row.get('next_action',''),row['scope'])
    return status+': '+clean['message']

class Selection:
    def __init__(self, checker, task, ids):
        self.checker,self.task,self.ids = checker,ident(task),list(ids)
        self.known=set(read(artifacts(checker)/'testcases'/task/'index.json')['cases'])
        self.path = safe(artifacts(checker),'config/selections/'+self.task+'/current.json')
        data = read(self.path) if self.path.exists() else {'format':1,'overrides':{}}
        self.overrides = self.validate(data)
    def validate(self,data):
        if not isinstance(data,dict) or data.get('format') != 1 or not isinstance(data.get('overrides'),dict):
            raise ValueError('Ungültiges Auswahlprofil')
        if any(type(value) is not bool for value in data['overrides'].values()): raise ValueError('ON/OFF muss boolesch sein')
        for key in data['overrides']: ident(key)
        return dict(data['overrides'])
    def on(self,test): return self.overrides.get(test,True)
    def selected(self): return [test for test in self.ids if self.on(test)]
    def set(self,ids,value):
        if type(value) is not bool or any(test not in self.ids for test in ids): raise ValueError('Unbekannte Auswahl')
        self.overrides.update({test:value for test in ids}); self.persist()
    def persist(self): write(self.path,{'format':1,'overrides':self.overrides})
    def reset(self): self.overrides={}; self.persist()
    def profile(self,name,load=False):
        ident(name)
        path = safe(artifacts(self.checker),'config/selections/'+self.task+'/profiles/'+name+'.json')
        if load:
            data=read(path); values=self.validate(data)
            if data.get('task_id') != self.task or any(k not in self.known for k in values):
                raise ValueError('Profil enthält unbekannte IDs oder fremde Aufgabe')
            # New IDs deliberately inherit ON. Functional changes are surfaced, not silently replayed.
            if data.get('catalog_hash') != digest(self.ids): print('Profilkatalog geändert: neue Fälle ON; vorhandene OFF bleiben erhalten.')
            self.overrides=values; self.persist()
        else:
            if path.exists(): raise ValueError('Profilname existiert; neuen Namen verwenden')
            write(path,{'format':1,'task_id':self.task,'catalog_hash':digest(self.ids),'source_hash':self.checker.manifest(self.task)['source_hash'],'overrides':self.overrides})

class CLI:
    def __init__(self,state,task=None,input_fn=input,output=print):
        self.checker=Checker(state)
        if not (self.checker.root/'config.json').is_file():
            raise ValueError('Checker-Registry fehlt: '+str(self.checker.root/'config.json')+'; vorhandenen Zustand wieder anbinden (cli/project.json). Kein Test gestartet.')
        self.task=task or self.checker.manifest()['task_id']
        self.task=ident(self.task); self.input,self.output=input_fn,output
        from source_discovery import discover
        self.source_discovery=discover(self.checker)
        # Entire catalog before filters, depth, readiness and submit.
        self.provision=materialize(self.checker,self.task)
        self.cases=self.checker.select('all',self.task)
        index=read(artifacts(self.checker)/'testcases'/self.task/'index.json')['cases']
        settings=artifacts(self.checker)/'config/project-cli.json'
        config=read(settings) if settings.exists() else {}
        provider=config.get('preflight_provider')
        supported=provider.get('supported_case_ids') if isinstance(provider,dict) else None
        if supported is not None and (not isinstance(supported,list) or any(not isinstance(x,str) or not x for x in supported)):
            raise ValueError('preflight_provider.supported_case_ids muss eine Liste von Fall-IDs sein')
        for c in self.cases:
            c['group']=index.get(c['test_id'],{}).get('group','Tests')
            c['blockers']=list(index.get(c['test_id'],{}).get('blockers',['Durable materialization conflict']))
            if supported is not None and c['test_id'] not in supported:
                c['blockers'].append('Automatische Projektvorprüfung unterstützt diesen Fall noch nicht; fallbezogenen Beobachtungsadapter implementieren.')
        self.selection=Selection(self.checker,self.task,[c['test_id'] for c in self.cases])
    def choose(self,value='on'):
        if value=='on': ids=self.selection.selected()
        elif value=='all': ids=[c['test_id'] for c in self.cases]
        elif value=='automatic': ids=[c['test_id'] for c in self.cases if not c['browser_required']]
        else:
            ids=[v.strip() for v in value.split(',')]
            if not all(ids) or len(ids)!=len(set(ids)): raise ValueError('Leere oder doppelte Auswahl')
        known={c['test_id']:c for c in self.cases}
        if any(k not in known for k in ids): raise ValueError('Unbekannte Testfall-ID')
        return [known[k] for k in ids]
    def plan(self,items):
        return {'task_id':self.task,'source_hash':self.checker.manifest(self.task)['source_hash'],
            'source_discovery':__import__('source_discovery').discover(self.checker),'provisioning':self.provision,'selected_count':len(items),'cases':[
                {'test_id':c['test_id'],'title':c['title'],'on':self.selection.on(c['test_id']),
                 'browser_required':c['browser_required'],'blockers':c['blockers'],
                 'durable':self.case_binding(c['test_id'])} for c in items]}
    def case_binding(self,test):
        try:return binding(self.checker,self.task,test)
        except (ValueError,KeyError,OSError) as error:return {'status':'CONFLICT','reason':str(error)}
    def gate(self):
        from source_discovery import discover, issues
        self.source_discovery=discover(self.checker)
        return list(dict.fromkeys(self.checker.verify(self.task)+issues(self.source_discovery)))
    def prevalidate(self,items,inputs,execution_scope='standalone'):
        if not items: raise ValueError('Leere Auswahl: kein Teststart')
        issues=self.gate()
        if issues: raise ValueError('; '.join(issues))
        if self.provision.get('installation_conflicts'):raise ValueError('CLI-Installationskonflikte: '+', '.join(self.provision['installation_conflicts']))
        for c in items:
            if execution_scope == 'campaign':
                from campaign_state import attached
                campaign=attached(self.checker)
                if campaign:campaign.test_start(self.task,c['test_id'])
            binding(self.checker,self.task,c['test_id'])
            from plan_registry import resolve_case
            c=resolve_case(self.checker,self.task,self.checker.select(c['test_id'],self.task)[0])
            from plan_registry import bind_parameters
            plan_for(c)
            c=bind_parameters(c,self.checker.cfg())
            from plan_registry import effective_llm_policy
            effective_llm_policy(c,self.checker.cfg())
            plan_for(c)
            spec=inputs.get(c['test_id'])
            if not isinstance(spec,dict) or not spec.get('preflight'): raise ValueError(c['test_id']+': frische Preflight-Datei fehlt')
            self.checker.preflight(c['test_id'],spec['preflight'],self.task,spec.get('baseline'))
    def submit(self,items,inputs):
        self.prevalidate(items,inputs)
        jobs=Jobs(self.checker.root); receipt={'task_id':self.task,'created_at':now(),'source_hash':self.checker.manifest(self.task)['source_hash'],'jobs':[],'status':'SUBMITTED'}
        for offset,c in enumerate(items):
            spec=inputs[c['test_id']]
            try: receipt['jobs'].append(jobs.submit(self.task,c['test_id'],spec['preflight'],spec.get('baseline'),execution_scope='standalone'))
            except Exception as error:
                created=getattr(error,'job_id',None)
                if created:
                    receipt['jobs'].append(jobs.view(created))
                    receipt['launch_pending_ids']=[created]
                receipt.update(status='PARTIAL_SUBMISSION',reason=type(error).__name__+': native submission interrupted; inspect receipt/jobs before retry',unsubmitted_ids=[x['test_id'] for x in items[offset+(1 if created else 0):]])
                break
        path=safe(artifacts(self.checker),'config/requests/receipt-'+uuid.uuid4().hex+'.json'); write(path,receipt)
        receipt['receipt_path']=str(path)
        return receipt
    def watch(self,receipt):
        jobs=Jobs(self.checker.root); prior=0
        try:
            while True:
                rows=[]; terminal=True
                for expected in receipt['jobs']:
                    job=jobs.load(ident(expected['job_id']))
                    if job['task_id']!=self.task or job['test_id']!=expected['test_id'] or job['source_hash']!=receipt['source_hash'] or job['queued_at']<receipt['created_at']:
                        raise ValueError('Fortschritt gehört nicht zu diesem Start')
                    terminal &= job['status'] in TERMINAL
                    value=job.get('percentage'); valid=type(value) in (int,float) and math.isfinite(value) and 0<=value<=100
                    # Native event percentage represents processed steps, independent of PASS.
                    value=value if valid else None
                    label='unbekannt' if value is None else f'{value:g}%'
                    filled=int(value/5) if value is not None else 0
                    rows.extend([job['test_id'],'['+'#'*filled+'-'*(20-filled)+'] '+label])
                visible=rows[:12]
                if sys.stdout.isatty() and prior: self.output(f'\x1b[{prior}A\x1b[J',end='')
                self.output('\n'.join(visible)); prior=len(visible)
                if terminal: return
                time.sleep(1)
        except KeyboardInterrupt: self.output('Anzeige getrennt; vorhandene Jobs laufen weiter.')
    def wizard(self):
        from source_discovery import discover, display
        self.output("Projekt: "+self.checker.cfg()["project"]+" | Testsatz: "+self.task)
        display(discover(self.checker),self.output)
        def option(title,choices):
            while True:
                self.output(title)
                for n,(label,_) in enumerate(choices,1): self.output(f'{n} {label}')
                self.output('0 Abbrechen')
                answer=self.input('> ').strip()
                if answer=='0': return None
                if answer.isdigit() and 1<=int(answer)<=len(choices): return choices[int(answer)-1][1]
                self.output('Ungültige Auswahl')
        depth=option('Prüftiefe', [('Schnell (ON-Fälle ohne Browser; ausgewiesener Teilumfang)','quick'),('Normal (alle ON-Fälle)','normal'),('Tief (alle ON-Fälle; vollständige Originalpläne)','deep')])
        if depth is None:return 0
        mode=option('Arbeitsmodus',[('Nur Befundung','verify'),('Mit Reparatur und erneuter Prüfung','repair')])
        if mode is None:return 0
        while True:
            self.output('Anzahl vollständiger Läufe (positive Ganzzahl)\n0 Abbrechen')
            raw=self.input('> ').strip()
            if raw=='0':return 0
            if raw.isdigit() and int(raw)>0: rounds=int(raw);break
            self.output('Positive Ganzzahl erforderlich')
        behavior=option('Fehlerverhalten',[('Fortsetzen und sammeln','continue'),('Nach fehlgeschlagenem Fall stoppen','stop'),('Pausieren und nachfragen','pause')])
        if behavior is None:return 0
        items=self.choose(); items=[c for c in items if depth!='quick' or not c['browser_required']]
        blockers=self.gate()
        blockers.extend('Materialisierungskonflikt: '+c['test_id'] for c in self.provision['conflicts'])
        blockers.extend('CLI-Installationskonflikt: '+p for p in self.provision.get('installation_conflicts',[]))
        if not items:blockers.append('Keine ON-Fälle im effektiven Umfang; Auswahl im Hauptmenü ändern')
        for c in items:
            blockers.extend(c['test_id']+': '+b for b in c['blockers'])
        self.output('Zusammenfassung')
        self.output('Prüftiefe: '+{'quick':'Schnell','normal':'Normal','deep':'Tief'}[depth])
        self.output(f'Läufe: {rounds}')
        self.output('Modus: '+('Nur Befundung' if mode=='verify' else 'Mit Reparatur'))
        if mode=='repair':self.output('Reparatur: direkter Codex App Server; Voraussetzungen erst am Reparaturschritt prüfen')
        self.output('Fehlerverhalten: '+{'continue':'Fortsetzen und sammeln','stop':'Nach Fehler stoppen','pause':'Pausieren und nachfragen'}[behavior])
        self.output('Tief erweitert keine OFF-Auswahl. Ohne zusätzlichen geprüften Tiefenplan bleiben die Originalpläne unverändert.')
        self.output(f'Ausgewählte Fälle: {len(items)}')
        for c in items[:12]:self.output('  '+c['test_id'])
        if len(items)>12:self.output(f'  … weitere {len(items)-12} Fälle; vollständiger Umfang in der Konfiguration')
        # Persist exact blockers below; summarize without changing case selection.
        grouped={}
        for c in items:
            for blocker in c['blockers']:
                reason=blocker.replace(c['test_id'], '<ID>')
                grouped.setdefault(reason, []).append(c['test_id'])
        case_blockers={c['test_id']+': '+b for c in items for b in c['blockers']}
        global_blockers=[b for b in blockers if b not in case_blockers]
        self.output(f'Voraussetzungen: {sum(bool(c["blockers"]) for c in items)} von {len(items)} Fällen BLOCKED')
        for reason in global_blockers[:6]:self.output('BLOCKED: '+reason)
        for reason, ids in list(grouped.items())[:6]:
            self.output(f'BLOCKED ({len(ids)} Fälle; '+', '.join(ids[:3])+(' …' if len(ids)>3 else '')+'): '+reason)
        remaining=max(0,len(global_blockers)-6)+max(0,len(grouped)-6)
        if remaining:self.output(f'Weitere {remaining} Ursachen in der vollständigen Konfiguration')
        request={'format':1,'task_id':self.task,'source_hash':self.checker.manifest(self.task)['source_hash'],
            'catalog_hash':digest([c['test_id'] for c in self.cases]),'test_ids':[c['test_id'] for c in items],
            'depth':depth,'mode':mode,'rounds':rounds,'error_behavior':behavior,'blockers':blockers,'status':'HANDOFF' if blockers else 'CONFIGURED'}
        self.output('1 Konfiguration speichern (kein Teststart)\n2 Tatsächlichen Start bestätigen\n0 Abbrechen')
        answer=self.input('> ').strip()
        if answer=='0':return 0
        if answer not in ('1','2'):self.output('Ungültig; kein Start');return 2
        path=safe(artifacts(self.checker),'config/requests/request-'+uuid.uuid4().hex+'.json');write(path,request)
        self.output('Konfiguration: '+str(path))
        if answer=='1':return 0
        self.output('Start bestätigt. Voraussetzungen werden vor jedem Fall und Durchlauf frisch geprüft.')
        if sys.platform=='win32':
            launcher=artifacts(self.checker)/'Start-Tests.ps1'
            completed=subprocess.run([shutil.which('pwsh') or shutil.which('powershell') or 'powershell','-NoProfile','-File',str(launcher),'-Command','run','-Task',self.task,
                '-Selection',','.join(c['test_id'] for c in items),'-Reviewed',
                '-Rounds',str(rounds),'-ErrorBehavior',behavior,'-Mode',mode,'-Interactive'],
                env={**os.environ,'TOOL_CHECKER_AUTOMATED_E2E':'1'})
            return completed.returncode
        from standalone_runs import run_rounds
        receipt=run_rounds(self,items,None,rounds,behavior,mode,automated_e2e=True)
        self.output(receipt['status']+' — '+receipt['report_path'])
        return 0 if receipt['status']=='PASS' else 2
    def prepare_case_inputs(self, case, round_number, retest=False):
        """Collect real fresh evidence through the explicitly configured project adapter."""
        issues=self.gate()
        if issues: raise ValueError('; '.join(issues))
        if self.checker.lock_path().exists():
            raise ValueError('Projekt durch laufende Prüfung gesperrt: '+str(self.checker.lock_path()))
        from plan_registry import resolve_case, bind_parameters
        resolved=resolve_case(self.checker,self.task,self.checker.select(case['test_id'],self.task)[0])
        plan_for(resolved)
        resolved=bind_parameters(resolved,self.checker.cfg())
        plan_for(resolved)
        config_path=artifacts(self.checker)/'config/project-cli.json'
        cfg=read(config_path) if config_path.exists() else {}
        provider=cfg.get('preflight_provider')
        if isinstance(provider,dict) and provider.get('supported_case_ids') is not None and case['test_id'] not in provider['supported_case_ids']:
            raise ValueError('Automatische Projektvorprüfung unterstützt '+case['test_id']+' noch nicht; fallbezogenen Beobachtungsadapter implementieren. Kein Test gestartet.')
        legacy=cfg.get('legacy_facade')
        if not provider and not legacy:
            raise ValueError('Automatische Vorprüfung ist für dieses Projekt nicht eingerichtet. '
                'In .tool-checker/config/project-cli.json einen geprüften preflight_provider oder die vorhandene legacy_facade anbinden; '
                'dieser muss Testumgebung, Rechte, Testdaten und gegebenenfalls Modell-Ausgangszustand tatsächlich prüfen. Kein Test gestartet.')
        timeout=provider.get('timeout',120) if isinstance(provider,dict) else 120
        if type(timeout) is not int or not 1<=timeout<=900:
            raise ValueError('preflight_provider.timeout muss zwischen 1 und 900 Sekunden liegen')
        if provider:
            if not isinstance(provider,dict) or provider.get('reviewed') is not True:
                raise ValueError('Automatische Vorprüfung benötigt einen geprüften Projektadapter (reviewed=true)')
            argv=provider.get('argv')
            if not isinstance(argv,list) or not argv or any(not isinstance(a,str) or not a for a in argv):
                raise ValueError('preflight_provider.argv muss eine nichtleere Argumentliste sein')
        else:
            if not isinstance(legacy,str) or not Path(legacy).is_absolute() or not Path(legacy).is_file():
                raise ValueError('Konfigurierte Projektvorprüfung fehlt: '+str(legacy))
            argv=[sys.executable,legacy,'preflight','--selection',case['test_id']]
        directory=safe(artifacts(self.checker),'runs/preflight/preflight-'+uuid.uuid4().hex)
        directory.mkdir(parents=True)
        output_path=directory/'inputs.json'
        request_path=directory/'request.json'
        started=now()
        write(request_path,{'format':1,'state':str(self.checker.root),'project':self.checker.cfg()['project'],
            'task_id':self.task,'test_id':case['test_id'],'source_hash':self.checker.manifest(self.task)['source_hash'],
            'contract_hash':case['contract_hash'],'round':round_number,'retest':retest,'started_at':started,
            'evidence_directory':str(directory),'case':resolved})
        command=[*argv,'--request',str(request_path),'--output',str(output_path)] if provider else [*argv,'--output',str(output_path)]
        self.output(case['test_id']+': Voraussetzungen prüfen (Lauf '+str(round_number)+')')
        try:
            with (directory/'adapter.log').open('w',encoding='utf-8') as log:
                environment=os.environ.copy()
                environment['PYTHONIOENCODING']='utf-8'
                result=subprocess.run(command,cwd=self.checker.cfg()['project'],stdout=log,stderr=subprocess.STDOUT,timeout=timeout,env=environment)
        except subprocess.TimeoutExpired:
            raise ValueError('Vorprüfung überschreitet '+str(timeout)+' Sekunden; Details: '+str(directory/'adapter.log')) from None
        if result.returncode:
            detail=read(output_path) if output_path.is_file() else {}
            if not detail:
                # Providers can safely reject an invalid output path without writing it.
                # Recover their structured final diagnostic; keep full logs local.
                for line in reversed((directory/'adapter.log').read_text(encoding='utf-8',errors='replace').splitlines()):
                    try: candidate=json.loads(line)
                    except ValueError: continue
                    if isinstance(candidate,dict) and candidate.get('status')=='BLOCKED' and isinstance(candidate.get('reason'),str):
                        detail=candidate;break
            reason=detail.get('reason','Exit '+str(result.returncode)) if isinstance(detail,dict) else 'Ungültige Adapterantwort'
            raise ValueError('Projektvorprüfung: '+str(reason)+'; Details: '+str(directory/'adapter.log'))
        if not output_path.is_file(): raise ValueError('Projektvorprüfung hat keine Nachweise geliefert; Details: '+str(directory/'adapter.log'))
        inputs=read(output_path)
        spec=inputs.get(case['test_id']) if isinstance(inputs,dict) else None
        if not isinstance(spec,dict) or not spec.get('preflight'):
            raise ValueError('Projektvorprüfung hat keinen Preflight für '+case['test_id']+' geliefert')
        spec=dict(spec)
        for key in ('preflight','baseline'):
            if spec.get(key):
                location=Path(spec[key])
                spec[key]=str(location if location.is_absolute() else directory/location)
        from datetime import datetime
        observed=datetime.fromisoformat(read(spec['preflight'])['checked_at'])
        if observed < datetime.fromisoformat(started):
            raise ValueError('Projektvorprüfung hat alte Nachweise wiederverwendet; frische Beobachtung erforderlich')
        self.prevalidate([case],{case['test_id']:spec},execution_scope='standalone')
        return spec
    def list_cases(self,base):
        items=list(base);page=0;size=10
        while True:
            shown=items[page*size:(page+1)*size]
            self.output(f'Testfälle: {len(items)}; Seite {page+1}')
            for n,c in enumerate(shown,1):self.output(f'{n} [{"ON" if self.selection.on(c["test_id"]) else "OFF"}] {c["test_id"]} {c["title"]}')
            self.output('Nummer/ID: umschalten\non/off <Nummern/IDs>: Mehrfachauswahl\nd<Nummer/ID>: Details\nn Nächste Seite\np Vorige Seite\n/query Suche\n/ Suche zurücksetzen\nb Zurück')
            raw=self.input('> ').strip()
            if raw=='b':return
            try:
                if not raw:continue
                if raw=='n':page=min(page+1,max(0,(len(items)-1)//size));continue
                if raw=='p':page=max(0,page-1);continue
                if raw.startswith('/') :items=fuzzy(base,raw[1:]);page=0;continue
                detail=raw.startswith('d'); token=raw[1:].strip() if detail else raw
                parts=token.split();mode=parts[0] if parts and parts[0] in ('on','off') else None
                refs=parts[1:] if mode else [token]
                selected=[]
                for ref in refs:
                    if ref.isdigit():
                        if not 1<=int(ref)<=len(shown):raise ValueError('Nummer außerhalb dieser Seite')
                        selected.append(shown[int(ref)-1])
                    else:
                        match=next((c for c in base if c['test_id']==ref),None)
                        if match is None:raise ValueError('Unbekannter Fall')
                        selected.append(match)
                if not selected:raise ValueError('Auswahl fehlt')
                if detail:
                    c=selected[0];self.output(f'{c["test_id"]}: {"ON" if self.selection.on(c["test_id"]) else "OFF"}')
                    lines=json.dumps(c,ensure_ascii=False,indent=2).splitlines()
                    for offset in range(0,len(lines),20):
                        self.output('\n'.join(lines[offset:offset+20]))
                        if offset+20<len(lines) and self.input('ENTER weitere Details; b zurück > ').strip()=='b':break
                elif mode:self.selection.set([c['test_id'] for c in selected],mode=='on')
                else:self.selection.set([selected[0]['test_id']],not self.selection.on(selected[0]['test_id']))
            except (ValueError,IndexError) as error:self.output(str(error))
    def menu(self):
        from source_discovery import discover, display
        self.output("Projekt: "+self.checker.cfg()["project"]+" | Testsatz: "+self.task)
        display(discover(self.checker),self.output)
        while True:
            self.output(f'Hauptmenü ({len(self.cases)} Fälle, {len(self.selection.selected())} ON)\n1 Testgruppen\n2 Suche\n3 Auswahlprofile\n4 Werkzeuge\n5 Startdialog\n0 Beenden')
            answer=self.input('> ').strip()
            try:
                if answer=='0':return 0
                if answer=='5':self.wizard()
                elif answer=='2':self.list_cases(fuzzy(self.cases,self.input('Suchtext > ')))
                elif answer=='1':
                    groups=sorted({c['group'] for c in self.cases})
                    while True:
                        self.output('Testgruppen')
                        for n,g in enumerate(groups,1):
                            cases=[c for c in self.cases if c['group']==g];count=sum(self.selection.on(c['test_id']) for c in cases)
                            state='ON' if count==len(cases) else 'OFF' if count==0 else 'gemischt'
                            self.output(f'{n} {g} [{state}] ({len(cases)})')
                        self.output('Nummer Gruppe öffnen\non/off <Nummer> gesamte Gruppe\nb Zurück')
                        raw=self.input('> ').strip()
                        if raw=='b':break
                        if not raw:continue
                        parts=raw.split();g=groups[int(parts[-1])-1] if parts[-1].isdigit() and 1<=int(parts[-1])<=len(groups) else None
                        if g is None:self.output('Unbekannte Gruppe');continue
                        cases=[c for c in self.cases if c['group']==g]
                        if parts[0] in ('on','off'):self.selection.set([c['test_id'] for c in cases],parts[0]=='on')
                        else:self.list_cases(cases)
                elif answer=='3':
                    self.output('1 Alle ON\n2 Alle OFF\n3 Zurücksetzen (aktive Fälle ON)\n4 Profil speichern\n5 Profil laden\n0 Zurück')
                    action=self.input('> ').strip()
                    if action in ('1','2'):self.selection.set(self.selection.ids,action=='1')
                    elif action=='3':self.selection.reset()
                    elif action in ('4','5'):self.selection.profile(self.input('Profilname > ').strip(),action=='5')
                elif answer=='4':
                    self.output('1 Katalog/Voraussetzungen\n2 Plan ON-Fälle\n3 Status/Kampagne\n4 Ergebnisse\n5 Export\n0 Zurück')
                    action=self.input('> ').strip()
                    if action in ('1','2'):self.output(json.dumps(self.plan(self.choose('all' if action=='1' else 'on')),ensure_ascii=False,indent=2))
                    elif action=='3':self.output(json.dumps({'gates':self.gate(),'jobs':Jobs(self.checker.root).list()},ensure_ascii=False,indent=2))
                    elif action=='4':self.output(json.dumps(self.results(),ensure_ascii=False,indent=2))
                    elif action=='5':self.export(self.input('Neuer JSON-Pfad > ').strip())
            except (ValueError,OSError,TypeError,json.JSONDecodeError) as error:self.output(str(error))
    def results(self):
        return [read(p) for p in (self.checker.task(self.task)/'results').glob('*/result.json')]
    def export(self,path):
        path=Path(path)
        if path.exists():raise ValueError('Export existiert; neue Datei verwenden')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8') as f:json.dump(self.plan(self.choose()),f,ensure_ascii=False,indent=2)

def case_entry(task,test,directory):
    parser=argparse.ArgumentParser(description='Dauerhafter Fall: Originalvertrag und native Jobs-Gates')
    parser.add_argument('--preflight');parser.add_argument('--baseline');parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();root=Path(directory).parents[2];state=read(root/'cli'/'project.json')['state'];cli=CLI(state,task)
    items=cli.choose(test)
    if not args.execute: print(json.dumps(cli.plan(items),ensure_ascii=False,indent=2));return 2 if items[0]['blockers'] else 0
    if not args.preflight:parser.error('--execute benötigt frische --preflight')
    receipt=cli.submit(items,{test:{'preflight':args.preflight,'baseline':args.baseline}})
    print(json.dumps(receipt,ensure_ascii=False,indent=2));return 0 if receipt['status']=='SUBMITTED' else 2

def main(argv=None):
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):
            stream.reconfigure(encoding='utf-8',errors='backslashreplace')
    p=argparse.ArgumentParser();p.add_argument('--state',required=True);p.add_argument('command',nargs='?',default='help')
    p.add_argument('--interactive',action='store_true');p.add_argument('--automated-e2e',action='store_true');p.add_argument('--rounds',type=int,default=1);p.add_argument('--behavior',choices=['continue','stop','pause'],default='continue');p.add_argument('--mode',choices=['verify','repair'],default='verify');p.add_argument('--task');p.add_argument('--selection',default='on');p.add_argument('--inputs');p.add_argument('--output');p.add_argument('--source');p.add_argument('--plugin-path');p.add_argument('--reviewed',action='store_true')
    args=p.parse_args(argv)
    args.automated_e2e = args.automated_e2e or os.environ.get('TOOL_CHECKER_AUTOMATED_E2E') == '1'
    if args.command=='help': print('menu | start (Dialog, kein Autostart) | plan | catalog | sources | markdown --source <Datei.md> | prepare-project | status | results | export | migrate | run\nMarkdown wird als Spezifikation inventarisiert; unvollständige Fälle bleiben Review-pflichtig/BLOCKED.');return 0
    try:
        if args.command in ('markdown','prepare-project'):
            from markdown_system import prepare_markdown, prepare_project
            state=Checker(args.state); project=Path(state.cfg()['project'])
            if args.output:output=Path(args.output)
            else:
                from datetime import datetime
                stamp=datetime.now().strftime('%Y%m%d')
                if args.command=='markdown' and args.source:
                    from markdown_system import sha256, slug
                    source=Path(args.source).resolve(strict=True)
                    name=stamp+'_src_'+slug(source.stem)+'_'+sha256(source)[:8]+'_test_system'
                else:name=stamp+'_src_project_test_system'
                output=artifacts(state)/'docs'/name
            if args.command=='markdown':
                if not args.source:raise ValueError('markdown benötigt --source <Datei.md>')
                result=prepare_markdown(args.source,output,state,args.task)
            else:result=prepare_project(project,output)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0
        if args.command=='sources':
            from source_discovery import discover, issues
            result=discover(Checker(args.state))
            if args.output:
                with Path(args.output).open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 2 if issues(result) else 0
        cli=CLI(args.state,args.task)
        if args.command=='menu':return cli.menu()
        if args.command=='start':return cli.wizard()
        if args.command=='migrate':result={'installation':install(cli.checker,reviewed=args.reviewed),'materialization':cli.provision,'selection_default':'ON; explizite OFF bleiben erhalten','archive':'Historical evidence unchanged; ambiguous archived scripts require reviewed ID/revision mapping'}
        elif args.command in ('plan','catalog'):result=cli.plan(cli.choose('all' if args.command=='catalog' else args.selection))
        elif args.command=='status':result={'gates':cli.gate(),'jobs':Jobs(cli.checker.root).list()}
        elif args.command=='results':result=cli.results()
        elif args.command=='export':cli.export(args.output);return 0
        elif args.command in ('prepare','preflight'):
            legacy=safe(artifacts(cli.checker),'config/project-cli.json')
            cfg=read(legacy) if legacy.exists() else {}
            if not cfg.get('legacy_facade'):raise ValueError('Projektbezogene '+args.command+'-Implementierung fehlt; native ingest/preflight verwenden')
            command=[sys.executable,cfg['legacy_facade'],args.command,'--selection',args.selection]
            for flag,value in (('--inputs',args.inputs),('--output',args.output),('--plugin',args.plugin_path)):
                if value:command.extend([flag,value])
            if args.reviewed:command.append('--reviewed')
            return subprocess.call(command)
        elif args.command=='run':
            if not args.reviewed:raise ValueError('run benötigt explizit --reviewed; start öffnet den Bestätigungsdialog')
            from standalone_runs import run_rounds
            result=run_rounds(cli,cli.choose(args.selection),read(args.inputs) if args.inputs else None,args.rounds,args.behavior,args.mode,
                              show_progress=args.interactive,automated_e2e=args.automated_e2e)
            if args.interactive:
                print(result["status"]+" — "+result["report_path"]);return 0 if result["status"]=="PASS" else 2
        else:raise ValueError('Unbekannter Befehl')
        if args.output:
            path=Path(args.output)
            with path.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 2 if isinstance(result,dict) and result.get('status') in ('PARTIAL_SUBMISSION','INCOMPLETE','NOT_STARTED','INPUT_REQUIRED') else 0
    except (ValueError,OSError,TypeError,KeyError) as error:print(json.dumps({'status':'BLOCKED','reason':str(error)},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())
