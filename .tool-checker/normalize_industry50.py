import hashlib, json, re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = Path('H:/OneDrive/Download/NETWORK_SIMULATOR_50_INDUSTRY_NEUTRAL_AGENT_MCP_TEST_SCENARIOS.md')
text = source.read_text(encoding='utf-8-sig')
old = json.loads((root/'.tool-checker/industry40.normalized.json').read_text(encoding='utf-8'))
manifest = {**old, 'source_hash': hashlib.sha256(source.read_bytes()).hexdigest(),
    'title': '50 industrieneutrale Agenten- und MCP-Prüfungen', 'test_cases': []}
manifest['global_rules'] = [text[text.index('## 3.'):text.index('# 4.')],
    text[text.index('# 8.'):text.index('# 19.')], text[text.index('# 20.'):]]
matches = list(re.finditer(r'^### (S\d{2}-[AB]) – (.+)$', text, re.M))
for i, m in enumerate(matches):
    end = matches[i+1].start() if i+1<len(matches) else text.index('# 7.')
    segment = re.split(r'\n## S\d|\n# [56]\.', text[m.end():end])[0].rstrip()
    raw = segment.replace('```text\n','').replace('```','').strip().removesuffix('---').strip()
    previous = next(c for c in old['test_cases'] if c['test_id']==m[1])
    assert raw == previous['input'], m[1]+' changed input'
    manifest['test_cases'].append({**previous, 'source_lines': [text[:m.start()].count('\n')+1,
        text[:m.end()+len(segment)].count('\n')+1], 'source_requirements':segment,
        'required_skills':['tool-checker'], 'required_tools':['NIS HTTP API','Browser'],
        'execution_plan': []})
integration = list(re.finditer(r'^## (S(?:2[1-9]|30)) – (.+)$',text,re.M))
prompts = {
 'S21':'Ich habe 3 Sensoren, 4 Aktoren und einen Raspberry Pi.\nErzeuge eine sinnvolle lokale Architektur.',
 'S22':'Prüfe die bestehende Architektur und stelle fest, ob ParkAssist mit DriverAssistance kommunizieren kann.',
 'S23':'Wie sind ParkAssist und DriverAssistance aktuell angebunden?',
 'S24':'Verbinde ParkAssist mit DriverAssistance.',
 'S25':'MCP-Schema-, Unsupported-, Timeout- und Kanalgrenzenprüfung',
 'S26':'Verbinde eine bestehende Funktion mit einem Zielcontroller, für den mehrere technisch valide Netzwerkoptionen existieren.',
 'S27':'Prüfe MotorRPM: 0 bis 5000 rpm, Auflösung 50 rpm, Zyklus 10 ms, CAN-FD; Message Binding verwendet 4 bit.',
 'S28':'Analysiere den Trace: Gateway Delay ab 12 s, Queue Growth, Message Delay, Deadline Miss.',
 'S29':'Bewerte SINGLE_POINT_OF_FAILURE am CentralGateway.',
 'S30':'Verbinde ParkAssist mit DriverAssistance, prüfe die Kommunikation in einer kurzen Simulation und analysiere auftretende Timingprobleme.'}
for i,m in enumerate(integration):
    end=integration[i+1].start() if i+1<len(integration) else text.index('# 20.')
    segment=text[m.end():end].strip()
    sections=list(re.finditer(r'^### (.+)$',segment,re.M))
    criteria=[h[1]+':\n'+segment[h.end():sections[j+1].start() if j+1<len(sections) else len(segment)].strip()
              for j,h in enumerate(sections) if h[1] not in {'Testeingabe','Browser klickt','Start','Ziel'}]
    manifest['test_cases'].append(dict(test_id=m[1],title=m[2],input=prompts[m[1]],
        source_lines=[text[:m.start()].count('\n')+1,text[:end].count('\n')],
        source_requirements=segment,difficulty='integration',variant='',architecture_variant='',
        mutating=True,browser_required=m[1] not in {'S22','S25'},
        preconditions=['Isolierter Teststack des veröffentlichten Images'],
        required_model_context=['Modellrevision und szenariospezifische Ausgangsdaten prüfen'],
        expected_questions=[],forbidden_questions=[],required_actions=['Originalfall ausführen und Nachweise sichern'],
        required_tools=['NIS HTTP API'],required_views=[],required_skills=['tool-checker'],
        expected_model_changes=[],expected_calculations=[],expected_validations=[],expected_visualizations=[],
        completion_criteria=criteria,failure_conditions=['Erfundene erfolgreiche Ausführung'],
        tags=['integration','mcp'],decision_mode='INTERACTIVE',overall_timeout=1800))
assert len(manifest['test_cases'])==50
(root/'.tool-checker/industry50.normalized.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'.tool-checker/industry50-ingest-review.json').write_text(json.dumps({
 'source_sha256':manifest['source_hash'],'count':50,'unchanged_AB_inputs':40,
 'read_sources':manifest['rule_files'],'policy':'No new architecture decisions; S07-B CAN-FD/Ethernet previously authorized. Documented integration choices require separate policy review.',
 'scope':'Fresh observations; no reuse of historical PASS as execution evidence.'},ensure_ascii=False,indent=2),encoding='utf-8')
print(manifest['source_hash'])
