"""Audit actual local inference evidence; never create or repair a product model."""
from pathlib import Path
import hashlib
import json
import re

WORK = Path(__file__).parent
SOURCE = Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt')


def main():
    evidence = json.loads((WORK / 'native-vehicle-parser-probe.json').read_text(encoding='utf-8'))
    if evidence['status'] != 'PASSED':
        raise SystemExit('Native probe is not complete; no audit success can be issued.')
    raw = SOURCE.read_bytes()
    source = raw.decode('utf-8')
    result = evidence['result']
    facts = result['interpretation']['components']
    technologies = result['interpretation']['technologies']
    def requirement_ids(text):
        text = re.sub('[\u2010\u2011\u2212]', '-', text)
        return set(re.findall(r'\bREQ[-_][A-Z]+[-_]\d+\b', text))
    ids = requirement_ids(source)
    retained = requirement_ids('\n'.join(f['source_quote'] for f in facts if f['kind'] == 'REQUIREMENT'))
    assert len(ids) == 168, len(ids)
    assert hashlib.sha256(raw).hexdigest() == evidence['source_sha256']
    assert ids <= retained, sorted(ids - retained)
    assert all(f['source_quote'] in source for f in facts)
    assert all(t['source_quote'] in source for t in technologies)
    assert not any(t['kind'] == 'TRANSPORT' and t['name'] in {'ADC', 'CDC', 'PDC', 'IDC', 'BDC'} for t in technologies)
    assert not any(f['kind'] in {'CATEGORY', 'INSTANCE'} and
                   re.search(r'Sensor.? und Aktorfehler|System verarbeitet|Controller.Design', f['source_quote'], re.I)
                   for f in facts)
    assert all(f['quantity'] is None for f in facts if f['kind'] == 'CATEGORY')
    output = {
        'status': 'PASSED', 'scope': 'native_original_document_parser_only',
        'source_sha256': evidence['source_sha256'], 'source_chars': len(source),
        'sections': len(result['segments']), 'actual_model_calls': len(evidence['calls']),
        'explicit_requirement_ids': len(ids), 'retained_requirement_ids': len(ids & retained),
        'fact_counts': {kind: sum(f['kind'] == kind for f in facts)
                        for kind in ['INSTANCE', 'CATEGORY', 'FUNCTION', 'REQUIREMENT']},
        'unknown_interfaces': [t['name'] for t in technologies if t['kind'] == 'UNRESOLVED'],
        'canonical_writes': False, 'wizard_execution': False, 'simulation': False,
    }
    (WORK / 'native-semantic-audit.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(output, ensure_ascii=True))


if __name__ == '__main__':
    main()
