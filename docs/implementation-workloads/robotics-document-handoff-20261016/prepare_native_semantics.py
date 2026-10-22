"""Prepare the next repair against the exact failed native-tested revision."""
from pathlib import Path
import hashlib
import json

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
work = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
STAGE = OUT / 'semantic-staged'
for relative, expected in work['revision_after'].items():
    data = (ROOT / relative).read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected, relative
    target = STAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    before = OUT / 'semantic-before' / relative
    before.parent.mkdir(parents=True, exist_ok=True)
    before.write_bytes(data)

def edit(relative, old, new):
    path = STAGE / relative
    text = path.read_text(encoding='utf-8')
    assert old in text, (relative, old[:100])
    path.write_text(text.replace(old, new), encoding='utf-8')

P = 'backend/nis/agent/orchestration/project_intake.py'
edit(P, "lines = selected[reference].splitlines()", "lines = component_units[reference]['text'].splitlines()")
edit(P, "item['source_quote'] = selected[reference]", "item['source_quote'] = component_units[reference].get('source_quote', selected[reference]) if field == 'components' else selected[reference]")
edit(P, "    if re.search(r'\\b(?:Funktionen?", "    # Bare architecture services describe logical responsibilities. Physical\n    # server/controller qualifiers retain their separately proven device role.\n    if re.fullmatch(r'\\s*(?:[-*]\\s*)?(?:Fleet Manager|Map|Traffic Service|MES|WMS-Anbindung|Rezept- und Batchsystem|Historian|Alarmmanagement|Materialfluss|Qualitätsmanagement|Werkerassistenz|Traceability|Energieplattform|Datenbank)\\s*\\.?\\s*', text, re.I):\n        return {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}\n    if re.search(r'\\b(?:Funktionen?")
edit(P, "rechner|steuergerät|steuerung)\\b", "rechner|steuergerät|steuerung|server|workstation)\\b")
edit(P, "    interface_section = None\n    markdown_path", "    interface_section = None\n    assurance_section = None\n    markdown_path")
edit(P, "        requirement_header = re.fullmatch", "        if heading and assurance_section is not None and not heading[1].startswith(assurance_section + '.'):\n            assurance_section = None\n        assurance_header = re.fullmatch(r'(?:Safety|Security|Sicherheit)(?:\\s*(?:,|/|&|und|and)\\s*(?:Safety|Security|Sicherheit|Qualität|Quality|Betrieb|Operations?))*\\s*:?\\s*', structural, re.I)\n        if assurance_header:\n            assurance_section = heading[1] if heading else ''\n        if assurance_section is not None and not assurance_header:\n            row_policy = {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}\n            normative_row = True\n        requirement_header = re.fullmatch")
# Atomic comma lists under explicit function headings. Every atom retains the
# complete original list citation; compound slash and English noun names stay.
edit(P, "        policies = [document_component_policy(clause) for clause in clauses]", "        function_list = bool(function_section is not None and not normative_row and not heading\n                             and len(clauses) > 1 and not re.search(r'\\b(?:muss|soll|shall|must|wenn|falls|if|when)\\b|[.!?]\\s+\\w', body, re.I))\n        if function_list:\n            last = re.split(r'\\s+und\\s+(?![^()]*\\))', clauses[-1])\n            if len(last) == 2 and all(last):\n                clauses = [*clauses[:-1], *last]\n            clauses = [re.sub(r'^[-*]\\s+', '', clause).strip().rstrip('.') for clause in clauses]\n        policies = [document_component_policy(clause) for clause in clauses]")
edit(P, "(prefix or architecture_section is not None or (mixed_hardware", "(function_list or prefix or architecture_section is not None or (mixed_hardware")
edit(P, "(f'.C{index + 1:02d}' if split else '')", "(f'.F{index + 1:02d}' if function_list else f'.C{index + 1:02d}' if split else '')")
edit(P, "'text': clause, 'policy': policy, 'required': required,", "'text': clause, **({'source_quote': text} if function_list else {}), 'policy': policy, 'required': required,")
edit(P, "if '.C' in u['source_ref'] or 'source_rows' in u", "if '.C' in u['source_ref'] or '.F' in u['source_ref'] or 'source_rows' in u")
edit(P, "['CATEGORY', 'FUNCTION', 'REQUIREMENT']}", "['CATEGORY', 'FUNCTION']}\n            branch['properties']['role'] = {'type': 'string', 'enum': ['OTHER']}")
# Preserve source offsets; only technology evidence from test/index scopes is
# ineligible. No source content is removed from the actual model request.
edit(P, "def document_transport_candidates(source: str, profiles, *, context_aliases=None, candidates=None):", '''def document_technology_source(source: str, *, scope_prefix=''):
    """Mask test/index mentions without changing source character positions."""
    from bisect import bisect_right
    offsets, contexts = document_source_contexts(scope_prefix + source)
    result, offset = [], len(scope_prefix)
    for line in source.splitlines(keepends=True):
        context = contexts[bisect_right(offsets, offset) - 1]
        excluded = any(re.match(r'^(?:\\d+(?:\\.\\d+)*[.)]?\\s+)?(?:Index|Inhaltsverzeichnis|Contents|Table of contents|Verifikation|Verification|Testfälle|Test cases)\\b', label, re.I) for label in context)
        excluded = excluded or bool(re.match(r'^\\s*[-*]?\\s*\\*{0,2}TC[-_]', line, re.I))
        result.append(''.join(char if char in '\\r\\n' else ' ' for char in line) if excluded else line)
        offset += len(line)
    return ''.join(result)


def document_transport_candidates(source: str, profiles, *, context_aliases=None, candidates=None, scope_prefix=''):''')
edit(P, "    text = re.sub(r'\\b' + _DOCUMENT_CONTROLLER_LABEL + r'\\s*\\([^)]+\\)', '', source, flags=re.I)", "    source = document_technology_source(source, scope_prefix=scope_prefix)\n    text = re.sub(r'\\b' + _DOCUMENT_CONTROLLER_LABEL + r'\\s*\\([^)]+\\)', '', source, flags=re.I)")
edit(P, "available_profiles = document_transport_candidates(source, profiles, context_aliases=source_aliases)", "available_profiles = document_transport_candidates(source, profiles, context_aliases=source_aliases, scope_prefix=scope_prefix)\n    eligible_source = document_technology_source(source, scope_prefix=scope_prefix)")
edit(P, "    for row in rows:\n        text = row['text']\n        labels", "    for row in rows:\n        text = row['text']\n        if text.strip() not in eligible_source:\n            continue\n        labels")
edit(P, "    semantic_errors = []\n    citation_errors", "    eligible_source = document_technology_source(source, scope_prefix=scope_prefix)\n    semantic_errors = []\n    for technology in result.technologies:\n        if technology.source_quote not in eligible_source:\n            semantic_errors.append(f'{technology.name}: Test-/Indexzitat belegt keine Projektschnittstelle.')\n    citation_errors")
edit(P, "document_transport_candidates(source, profiles, context_aliases=context_aliases)\n", "document_transport_candidates(source, profiles, context_aliases=context_aliases, scope_prefix=scope_prefix)\n")
edit(P, "for qualified in document_qualified_transports(source, profiles):", "for qualified in document_qualified_transports(eligible_source, profiles):")
edit(P, "lambda match: ' ' * len(match.group()), source)", "lambda match: ' ' * len(match.group()), eligible_source)")
edit(P, "_DOCUMENT_CONTROLLER_LABEL + r'\\s*\\(([A-Z][A-Z0-9_-]{1,15})\\)', source, re.I):\n        if not any", "_DOCUMENT_CONTROLLER_LABEL + r'\\s*\\(([A-Z][A-Z0-9_-]{1,15})\\)', eligible_source, re.I):\n        if not any")
edit(P, "        if component.kind == 'INSTANCE' and policy is None:", "        if policy is None and component.kind in {'INSTANCE', 'CATEGORY'} and component.role != 'OTHER':\n            semantic_errors.append(f'{component.name}: unbelegte Geräterolle; OTHER und explizite Klärung erforderlich.')\n        if component.kind == 'INSTANCE' and policy is None:")
edit(P, "if not any(piece in item.source_quote and (not unit['policy']", "if not any(piece in item.source_quote and item.source_context == unit['source_context'] and (not unit.get('source_quote') or item.name == unit['text'][:120]) and (not unit['policy']")
edit(P, "if item.source_quote == unit['text'] and (item.kind", "if item.source_context == unit['source_context'] and item.source_quote == unit.get('source_quote', unit['text']) and (item.kind")

P = 'frontend/src/features/agent/lib/document-clarification.ts'
edit(P, 'item.source_quote.includes(question.source_quote)', 'item.source_quote === question.source_quote')
edit(P, "  for (const fact of facts.filter(fact => fact.kind === 'FUNCTION')) {\n    const candidates", "  for (const fact of facts.filter(fact => fact.kind === 'FUNCTION')) {\n    const sharedCitation = facts.some(other => other.kind === 'FUNCTION' && other.name !== fact.name && other.source_quote === fact.source_quote && JSON.stringify(other.source_context ?? []) === JSON.stringify(fact.source_context ?? []));\n    const candidates")
edit(P, "fact.source_quote.includes(duty.source_quote)))", "fact.source_quote.includes(duty.source_quote) && (!sharedCitation || duty.source_quote.includes(fact.name))))")

P = 'frontend/src/features/agent/lib/engineering-specification.ts'
edit(P, "const mayUseProjectInterface = isEngineeringControllerDevice(declaredType)\n", "const mayUseProjectInterface = !entry.documentEvidence && (isEngineeringControllerDevice(declaredType)\n")
edit(P, "|| (legacyConfirmed && communicationSystems.length === 1);", "|| (legacyConfirmed && communicationSystems.length === 1));")
# Only a unique controller declaration heading opens a participant's body.
# An architecture list entry such as Hauptrechner does not own the whole chapter.
edit(P, "  const documentIdentityPeers =", '''  const reviewedSourceLines = (item: { source_quote: string; source_context?: string[] }) => {
    const matches = lines.map((line, index) => ({ line, index })).filter(({ line }) =>
      /^(?:\\s*#{1,6}\\s+|\\s*\\d+(?:\\.\\d+)*[.)]?\\s+)/.test(line)
      && line.trim().replace(/^#{1,6}\\s+/, '') === item.source_quote.trim().replace(/^#{1,6}\\s+/, ''));
    if (matches.length !== 1) return [item.source_quote];
    const start = matches[0].index;
    const heading = lines[start].trim();
    const markdownLevel = heading.match(/^(#{1,6})\\s+/)?.[1].length;
    const number = heading.match(/^(\\d+(?:\\.\\d+)*)[.)]?\\s+/)?.[1];
    const boundary = lines.findIndex((line, index) => {
      if (index <= start) return false;
      const next = line.trim();
      const nextLevel = next.match(/^(#{1,6})\\s+/)?.[1].length;
      const nextNumber = next.match(/^(\\d+(?:\\.\\d+)*)[.)]?\\s+/)?.[1];
      return Boolean(markdownLevel && nextLevel && nextLevel <= markdownLevel)
        || Boolean(number && nextNumber && !nextNumber.startsWith(number + '.'));
    });
    return lines.slice(start, boundary >= 0 ? boundary : lines.length);
  };
  const documentIdentityPeers =''')
edit(P, "lines: existing?.lines ?? [name]", "lines: existing?.lines ?? reviewedSourceLines(item)")

P = 'backend/nis/agent/tools/wizard_generation.py'
edit(P, "        candidates = set()\n        for chain", "        shared_citation = any(other['name'] != fact['name'] and other['source_quote'] == fact['source_quote'] and other.get('source_context', []) == fact.get('source_context', []) for other in duties)\n        candidates = set()\n        for chain")
edit(P, "and duty['source_quote'] in fact['source_quote']\n", "and duty['source_quote'] in fact['source_quote'] and (not shared_citation or fact['name'] in duty['source_quote'])\n")
edit(P, "if row.get('hardware_node_id') == host_ref and len(quote) >= 3 and quote in duty['source_quote']:", "if row.get('hardware_node_id') == host_ref and len(quote) >= 3 and quote in duty['source_quote'] and (not any(other.get('kind') == 'FUNCTION' and other.get('source_quote') == duty['source_quote'] and other.get('name') != duty['name'].rsplit(' [', 1)[0] and other.get('source_context', []) == duty.get('source_context', []) for other in (document_evidence or {}).get('components', [])) or duty['name'].rsplit(' [', 1)[0] in quote):")

P = 'frontend/src/features/agent/ui/agent-chat-core.tsx'
edit(P, "{!equipmentIdentityReady && <p role=\"alert\">Geräteumfang noch unvollständig:", "{!equipmentIdentityReady && EQUIPMENT_CATEGORIES.some(({ key }) => identifiedCounts[key] !== equipmentCounts[key]) && <p role=\"alert\">Geräteumfang noch unvollständig:")
print(json.dumps({'status': 'STAGED', 'directory': str(STAGE)}))
