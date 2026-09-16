import hashlib, json, re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=Path('H:/OneDrive/Download/NETWORK_SIMULATOR_60_INDUSTRY_NEUTRAL_AGENT_MCP_TRACE_TEST_SCENARIOS.md')
text=source.read_text(encoding='utf-8-sig')
previous=json.loads((root/'.tool-checker/industry50.normalized.json').read_text(encoding='utf8'))
m={**previous,'source_hash':hashlib.sha256(source.read_bytes()).hexdigest(),'title':'60 industrieneutrale Agenten-, MCP- und Trace-Prüfungen','test_cases':[]}
m['global_rules']=[text[text.index('## 3.'):text.index('# 4.')],text[text.index('# 8.'):text.index('# 19.')],text[text.index('# 20.'):text.index('# 23.')],text[text.index('# 24.'):]]
for old in previous['test_cases']:
    case={**old,'execution_plan':[]}
    pattern=r'^#{2,3} '+re.escape(case['test_id'])+r' – .+$'
    hit=re.search(pattern,text,re.M); assert hit,case['test_id']
    next_heading=re.search(r'^#{1,3} (?:S\d|\d+\.)',text[hit.end():],re.M)
    end=hit.end()+next_heading.start() if next_heading else len(text)
    segment=text[hit.end():end].strip()
    assert old['source_requirements'].strip().removesuffix('---').strip()==segment.removesuffix('---').strip(),case['test_id']
    case.update(source_lines=[text[:hit.start()].count('\n')+1,text[:end].count('\n')],source_requirements=segment)
    m['test_cases'].append(case)
trace=list(re.finditer(r'^## (S(?:3[1-9]|40)) – (.+)$',text,re.M))
for i,hit in enumerate(trace):
    end=trace[i+1].start() if i+1<len(trace) else text.index('# 24.')
    segment=text[hit.end():end].strip().removesuffix('---').strip()
    m['test_cases'].append(dict(test_id=hit[1],title=hit[2],input=segment,
        source_lines=[text[:hit.start()].count('\n')+1,text[:end].count('\n')],source_requirements=segment,
        difficulty='integration',variant='',architecture_variant='',mutating=True,browser_required=hit[1] in {'S32','S33','S34','S35','S39','S40'},
        preconditions=['Isolierter Teststack des veröffentlichten Images'],required_model_context=['Modellrevision und szenariospezifische Ausgangsdaten prüfen'],
        expected_questions=[],forbidden_questions=[],required_actions=['Originalfall ausführen und Nachweise sichern'],required_tools=['NIS HTTP API'],required_views=[],required_skills=['tool-checker'],
        expected_model_changes=[],expected_calculations=[],expected_validations=[],expected_visualizations=[],completion_criteria=[segment],
        failure_conditions=['Erfundene erfolgreiche Ausführung'],tags=['integration','mcp','trace'],decision_mode='INTERACTIVE',overall_timeout=1800,execution_plan=[]))
assert len(m['test_cases'])==60
for name in ['python_core/11_TRACE_CORE.md','simulation/13_TRACE_INTEGRATION.md','TRACE_IMPORT.md']:
    m['rule_files'].append(str(root/'docs'/name))
(root/'.tool-checker/industry60.normalized.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf8')
(root/'.tool-checker/industry60-ingest-review.json').write_text(json.dumps({'count':60,'unchanged_cases':50,'read_sources':m['rule_files'],'source_hash':m['source_hash'],'policy':'No new architecture decisions. Fresh execution evidence required. Source sections 1/22 have stale totals; section25 and enumerated cases define60.'},ensure_ascii=False,indent=2),encoding='utf8')
print(m['source_hash'])
