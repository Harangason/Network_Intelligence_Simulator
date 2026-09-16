import hashlib, json, re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = Path('H:/OneDrive/Download/NETWORK_SIMULATOR_40_INDUSTRY_NEUTRAL_AGENT_TEST_SCENARIOS.md')
text = source.read_text(encoding='utf-8-sig')
matches = list(re.finditer(r'^### (S\d{2}-[AB]) – (.+)$', text, re.M))
assert len(matches) == 40
global_intro = text[text.index('## 3.'):text.index('# 4.')]
global_tail = text[text.index('# 8.'):]
metrics = ['Typing Accuracy','Correct Existing-Object Reuse','Architecture Validity','Correct Questions','Unnecessary Question Count','Device Classification Accuracy','Technology Compatibility','Port / Interface Validity','Routing Completeness','Transport Completeness','Capacity Validation','Timing Validation','Blocking Findings','Completion Accuracy','Hallucinated Objects','Duplicate Objects']
architectures = ['V0','V0','V1','V2','V3','V4','KI 2+3','V4','V2','V2','V3','KI 2+3','V1','V4','V4','V2','V3','V0/V2','V4 + KI 2+3','Hybrid']
cases=[]
for i,m in enumerate(matches):
    n=int(m[1][1:3]); variant=m[1][-1]
    end=matches[i+1].start() if i+1<len(matches) else text.index('# 7.')
    segment=text[m.end():end]
    segment=re.split(r'\n## S\d|\n# [56]\.',segment)[0].rstrip()
    span_end=m.end()+len(segment)
    heading=list(re.finditer(r'^## S\d{2} – (.+)$',text[:m.start()],re.M))[-1][1]
    # Preserve the exact input AND explanatory requirements after its code block.
    raw=segment.replace('```text\n','').replace('```','').strip().removesuffix('---').strip()
    checks=['Technisch begründete Architektur und nachvollziehbare Entscheidungen', 'Vollständige Validierung ohne offene Identifier-Konflikte', 'Keine Fertigmeldung ohne vollständige fachliche Artefakte', 'Wiederholung verwendet bestehende passende Objekte ohne Duplikate']
    if n>=19: checks+=['Workload, Work Packages, Batch Generation, Batch Validation und Global Reconciliation belegt']
    if n==20: checks+=['Reproduzierbare Simulation und nach Source, Destination, Address, Function, Transport, Payload, Network, Route auflösbarer Trace']
    cases.append(dict(test_id=m[1],title=heading+' – '+variant,input=raw,source_lines=[text[:m.start()].count('\n')+1,text[:span_end].count('\n')+1],source_requirements=segment,difficulty='simple' if n<=5 else 'medium' if n<=18 else 'complex',variant=variant,architecture_variant=architectures[n-1],mutating=True,browser_required=True,preconditions=['Isoliertes leeres Testprojekt auf geprüftem Build'],required_model_context=['Kanonisches Inventar und Modellrevision vor Ausführung'],expected_questions=[],forbidden_questions=['Wie soll Sensor 1 heißen?'],required_actions=['Modellkontext erfassen','Originalauftrag an Engineering-Agent senden','Agentenantwort und Persistenz prüfen','Ergebnis im Browser prüfen'],required_tools=['NIS HTTP API','Playwright'],required_views=['Engineering'],required_skills=['tool-checker'],expected_model_changes=['Hardware, Funktionen, Zuordnungen, Interfaces, Ports, Netze, Payloads und Transport gemäß Originalauftrag'],expected_calculations=['Capacity, Timing und gegebenenfalls Gateway Load getrennt belegt'],expected_validations=['Typing, Technologiekompatibilität, Ports, Transport, Routing und Simulation Preflight validiert'],expected_visualizations=['Netzwerk- und Routingdarstellung passend zum gespeicherten Modell'],completion_criteria=checks,failure_conditions=['Fachfremde Automotive-Zuordnung ohne Begründung','Erfundene bestätigte Hardwarefakten oder Kodierungen','Unnötige Delegation der Engineering-Ausführung an den Nutzer'],metrics=metrics,tags=['industry-neutral',f'pair:S{n:02d}'],decision_mode='INTERACTIVE',overall_timeout=1800))
rules=['SPATIAL_ARCHITECTURE_CONTRACT.md','COMMUNICATION_DESIGN_CONTRACT.md','NETWORK_NAMING_CONTRACT.md','WIZARD_EXECUTION_CONTRACT.md','WIZARD_RELEASE_GATE.md','agent_core/16_MODEL_AWARE_EXECUTION.md','device_classification/02_TYPINGS.md','device_classification/03_DATA_COMPLEXITY.md','technology_bindings/00_OVERVIEW.md','addressing/02_ADDRESS_POLICY.md']
manifest=dict(source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),title='40 industrieneutrale Engineering-Szenarien',domain='engineering',purpose='A/B-Akzeptanzprüfung der vollständigen Engineering-Pipeline',global_rules=[global_intro,global_tail],architecture_rules=[text[text.index('## 2.'):text.index('## 3.')]],rule_files=[str(root/'docs'/p) for p in rules],required_skills=[],required_tools=[],required_views=[],required_outputs=['Originalantwort und persistierter Modellzustand'],test_cases=cases)
out=root/'.tool-checker/industry40.normalized.json'
out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'.tool-checker/ingest-review.json').write_text(json.dumps(dict(source_sha256=manifest['source_hash'],count=len(cases),variants={'A':20,'B':20},docs_search='Recursive rg docs: Typing|REUSE|Data Complexity|Technology Binding|industry.neutral',read_sources=manifest['rule_files'],unavailable=[],execution_scope='Original prompts through real agent HTTP and browser; follow-up only when source provides answer; no invented engineering approvals'),ensure_ascii=False,indent=2),encoding='utf-8')
print(out)
