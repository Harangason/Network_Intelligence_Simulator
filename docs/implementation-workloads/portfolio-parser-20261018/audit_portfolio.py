"""Read-only checks of original portfolio sources; no model or inference writes."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import os
import importlib.util

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration import project_intake as intake

if '--baseline' in sys.argv:
    os.environ['PORTFOLIO_STAGED_INTAKE'] = str(Path(__file__).resolve().parent / 'before/backend/nis/agent/orchestration/project_intake.py')

if os.environ.get('PORTFOLIO_STAGED_INTAKE'):
    from backend.nis.agent.tools.inventory_quantities import VOCABULARY
    vocabulary_path = Path(os.environ['PORTFOLIO_STAGED_INTAKE']).parents[2] / 'domain/inventory-vocabulary.json'
    VOCABULARY.update(json.loads(vocabulary_path.read_text(encoding='utf-8')))
    spec = importlib.util.spec_from_file_location('portfolio_staged_intake', os.environ['PORTFOLIO_STAGED_INTAKE'])
    intake = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = intake
    spec.loader.exec_module(intake)

BASE = Path(r'C:\Users\marti\PycharmProjects\Benchmark_Modelle')
PACKAGE = BASE / 'INDUSTRIEPORTFOLIO_100_KATEGORIENPAKET'
OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile_audit(source, label):
    rows = intake.document_source_references(source)
    units = intake.document_component_sources(rows)
    scopes = sorted({tuple(intake.document_system_scope(unit['source_context']))
                     for unit in units if unit['policy'] and unit['policy']['kind'] != 'REQUIREMENT'})
    retained = '\n'.join(unit['text'] for unit in units
                         if unit['policy'] and unit['policy']['kind'] == 'REQUIREMENT')
    requirements = sorted(set(re.findall(r'\bREQ-[\w-]+', source)))
    issues = []
    headings = list(re.finditer(r'^(#{1,6})\s+(.+)$', source, re.M))
    for index, heading in enumerate(headings):
        title = re.sub(r'^\d+(?:\.\d+)*[.)]?\s+', '', heading[2])
        if not re.fullmatch(r'Kernfunktionen|Core functions', title, re.I):
            continue
        end = next((item.start() for item in headings[index + 1:]
                    if len(item[1]) <= len(heading[1])), len(source))
        lines = [line.strip() for line in source[heading.end():end].splitlines()
                 if re.match(r'^\s*[-*]\s+', line)]
        for line in lines:
            witnesses = [unit for unit in units if unit['text'] == line
                         or unit.get('source_quote') == line]
            if not any(unit['required'] and unit['policy']
                       and unit['policy']['kind'] == 'FUNCTION' for unit in witnesses):
                issues.append({'code': 'CORE_FUNCTION_NOT_REQUIRED', 'quote': line,
                               'chapter': heading[2], 'actual': witnesses})
    for unit in units:
        if unit['required'] and unit['policy'] is None:
            issues.append({'code': 'UNCLASSIFIED_REQUIRED_COMPONENT', 'severity': 'MODEL_CLASSIFICATION_REQUIRED', 'unit': unit})
        if unit['policy'] and unit['policy']['kind'] == 'FUNCTION' and re.match(r'^ISO\s+\d+', unit['text']):
            issues.append({'code': 'STANDARD_OFFERED_AS_FUNCTION', 'unit': unit})
    function_table = False
    for line in source.splitlines():
        text = line.strip()
        if not text:
            continue
        if not text.startswith('|'):
            function_table = False
            continue
        cells = [cell.strip() for cell in text.strip('|').split('|')]
        if any(re.fullmatch(r'Funktionsgruppe|Funktion|Function group|Function', cell, re.I) for cell in cells):
            function_table = True
            continue
        if not function_table or all(re.fullmatch(r'[: -]+', cell) for cell in cells):
            continue
        if not any(unit['required'] and unit['policy'] and unit['policy']['kind'] in {'FUNCTION', 'REQUIREMENT'}
                   and (text in unit['text'] or text in unit.get('source_quote', '')) for unit in units):
            issues.append({'code': 'FUNCTION_TABLE_ROW_NOT_REQUIRED', 'quote': text})
    requirement_lines = [line.strip() for line in source.splitlines() if re.search(r'\bREQ-[\w-]+', line)]
    for line in requirement_lines:
        if line not in retained:
            issues.append({'code': 'REQUIREMENT_LINE_NOT_RETAINED', 'quote': line})
    return {'label': label, 'source_chars': len(source),
            'source_utf8_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'source_reconstruction_exact': ''.join(row['text'] for row in rows) == source,
            'counts': dict(Counter(unit['policy']['kind'] if unit['policy'] else 'UNCLASSIFIED'
                                   for unit in units)),
            'system_scopes': scopes, 'requirement_ids': requirements,
            'missing_requirement_ids': [key for key in requirements if key not in retained],
            'issues': issues}


def main():
    overall = PACKAGE / 'INDUSTRIEPORTFOLIO_100_VOLLSTAENDIGE_SYSTEMPROFILE.md'
    source = overall.read_bytes().decode('utf-8')
    headings = list(re.finditer(r'^## (\d{3})\. (.+)$', source, re.M))
    profiles = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(source)
        appendix = re.search(r'^#{1,2} Anhang\b', source[heading.end():end], re.M)
        if appendix:
            end = heading.end() + appendix.start()
        profiles.append(profile_audit(source[heading.start():end], heading[1] + '. ' + heading[2]))
    originals = [profile_audit((BASE / 'Fahrzeug komplett.txt').read_bytes().decode('utf-8'), 'Fahrzeug komplett.txt'),
                 profile_audit((PACKAGE / 'D_INDUSTRIAL_ROBOTICS_054_063.md').read_bytes().decode('utf-8'), 'D_INDUSTRIAL_ROBOTICS_054_063.md')]
    result = {'status': 'ANALYZED_WITH_FINDINGS', 'at_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'Deterministic parser/schema audit, NOT native Qwen or model/simulation acceptance',
              'canonical_writes': False, 'inference_calls': 0,
              'original_vehicle_raw_sha256': digest(BASE / 'Fahrzeug komplett.txt'),
              'parser_sha256': digest(Path(os.environ.get('PORTFOLIO_STAGED_INTAKE', str(ROOT / 'backend/nis/agent/orchestration/project_intake.py')))),
              'sources': [{'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}
                          for path in sorted(PACKAGE.glob('*.md'))],
              'profiles': profiles, 'current_native_originals': originals}
    target = OUT / ('baseline-expanded-audit.json' if '--baseline' in sys.argv else
                    'staged-audit.json' if os.environ.get('PORTFOLIO_STAGED_INTAKE') else 'canonical-audit.json')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'profiles': len(profiles),
                      'profiles_with_findings': sum(bool(item['issues']) for item in profiles),
                      'coverage_findings': sum(issue['code'] != 'UNCLASSIFIED_REQUIRED_COMPONENT' for item in profiles for issue in item['issues']),
                      'missing_requirement_ids': sum(len(item['missing_requirement_ids']) for item in profiles),
                      'issues': dict(Counter(issue['code'] for item in profiles for issue in item['issues'])),
                      'originals': [{'label': item['label'], 'source_chars': item['source_chars'],
                                    'issues': dict(Counter(issue['code'] for issue in item['issues']))} for item in originals],
                      'evidence': str(target)}, ensure_ascii=True))


if __name__ == '__main__':
    main()
