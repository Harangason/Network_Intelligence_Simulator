"""Keep complete reviewed facts in the existing proposal source evidence."""
from pathlib import Path

OUT = Path(__file__).parent
TARGET = OUT / 'staged/backend/nis/agent/orchestration/project_intake.py'
text = TARGET.read_text(encoding='utf-8')
text = text.split('\n\ndef reviewed_document_evidence(', 1)[0]
text += '''

def reviewed_document_evidence(prompt: str):
    """Validate the reviewed source snapshot before ordinary model proposal use.

    The original source, typed facts and review answers share the existing
    document-equipment envelope. This performs no model writes or approvals.
    """
    import hashlib
    import json
    matches = list(re.finditer(r'^- Dokument-Geräte:\\s*([^\\r\\n]+)$', prompt, re.M))
    if not matches:
        return None
    match = matches[-1]
    value = json.loads(match[1])
    if not isinstance(value, dict) or 'facts' not in value:
        return None  # Existing quantity-only review envelopes remain supported.
    source = value.get('source_text')
    if not isinstance(source, str) or not source or len(source) > DOCUMENT_SOURCE_MAX_CHARS:
        raise ValueError('Vollständige Dokumentquelle für die geprüften Befunde fehlt.')
    digest = hashlib.sha256(source.encode('utf-8')).hexdigest()
    if value.get('source_sha256') != digest or value.get('source_chars') != len(source):
        raise ValueError('Geprüfte Dokumentbefunde gehören nicht zu dieser vollständigen Quelle.')
    outside = prompt[:match.start()] + prompt[match.end():]
    facts = value.get('facts')
    technologies = value.get('technologies')
    if not isinstance(facts, list) or not isinstance(technologies, list):
        raise ValueError('Strukturierte Dokumentbefunde sind unvollständig.')
    for item in [*facts, *technologies]:
        if not isinstance(item, dict) or not item.get('source_quote') or item['source_quote'] not in outside:
            raise ValueError('Ein Dokumentbefund ist nicht in der ursprünglichen Auftragsquelle belegt.')
    interpretation = validate_document_interpretation({
        'summary': 'Geprüfte quellengebundene Dokumentbefunde.',
        'components': facts, 'technologies': technologies,
        'proposed_task': 'Quellenbefunde im normalen Modellvorschlag prüfen; offene Zuordnungen und Mengen nicht ergänzen.',
        'assumptions': [], 'open_questions': ['Offene Angaben bleiben vor Modellfreigabe zu klären.'],
    }, source, aggregate=True)
    return {'source': 'reviewed_document', 'source_name': value.get('source_name'),
            'source_sha256': digest, 'source_chars': len(source),
            'components': interpretation['components'], 'technologies': interpretation['technologies'],
            'questions': value.get('questions', []), 'answers': value.get('answers', []),
            'excluded_questions': value.get('excluded_questions', []),
            'canonical_writes': False, 'approval_required': True}
'''
TARGET.write_text(text, encoding='utf-8')

REL = 'backend/nis/agent/tools/wizard_generation.py'
text = (OUT / 'before' / REL).read_text(encoding='utf-8')
needle = "def generate(arguments: dict, *, source_evidence: list[dict] | None = None) -> dict:\n"
assert text.count(needle) == 1
text = text.replace(needle, needle + "    from backend.nis.agent.orchestration.project_intake import reviewed_document_evidence\n    document_evidence = reviewed_document_evidence(arguments.get('prompt', ''))\n    if document_evidence is not None:\n        source_evidence = [*(source_evidence or []), document_evidence]\n")
text = text.replace("wizard-model-v25-document-scoped-functions", "wizard-model-v26-reviewed-document-facts")
(OUT / 'staged' / REL).write_text(text, encoding='utf-8')
print('Staged server source-evidence validation prepared; no application mutation.')
