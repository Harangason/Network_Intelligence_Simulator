"""Prepare the reviewed parser repair outside frozen application sources."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent / 'staged'


def stage(relative, change):
    text = (ROOT / relative).read_text(encoding='utf-8')
    revised = change(text)
    assert revised != text, relative
    target = OUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(revised, encoding='utf-8')


def replace(text, old, new):
    assert text.count(old) == 1, old[:150]
    return text.replace(old, new)


def parser(text):
    anchor = "    role = None\n"
    text = replace(text, anchor, r'''    # Actions describe behavior even when their objects contain hardware words.
    # Apply before lexical device detection, without treating noun declarations
    # such as "Motorcontroller (MC)" as capabilities.
    if not any(quantities(text).values()) and not document_device_aliases(text) and re.search(r'\b(?:erkennen|behandeln|verarbeitet|verarbeiten|steuert|steuern|erfasst|erfassen|überwachen|überwacht|bereitstellen|bereitstellt|protokollieren|sicherstellen|verwalten|detects?|process(?:es)?|controls?|monitors?|provides?)\b', text, re.I):
        return {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}
    if re.search(r'\b(?:Sensorlinks?|sensor links?|Punkt-zu-Punkt-Links|point-to-point links?)\b', text, re.I):
        return {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}
    role = None
''')
    text = replace(text, '    excluded_section = None\n    context_rows =', '    excluded_section = None\n    requirement_section = None\n    requirement_lead = False\n    context_rows =')
    anchor = "        structural = heading[2] if heading else text\n"
    text = replace(text, anchor, anchor + r'''        requirement_header = re.fullmatch(r'(?:Anforderungen|Requirements)\s*:?\s*', structural, re.I)
        if requirement_header:
            requirement_section = heading[1] if heading else ''
            requirement_lead = False
        elif heading and requirement_section is not None and (not requirement_section or not heading[1].startswith(requirement_section + '.')):
            requirement_section = None
            requirement_lead = False
        elif re.fullmatch(r'(?:Hardware|Architektur|Architecture|Interfaces|Schnittstellen|Aufgaben|Responsibilities|Funktionen|Functions)\s*:', structural, re.I):
            requirement_section = None
            requirement_lead = False
        if re.fullmatch(r'(?:Das System|The system)\s+(?:muss|must|shall)\s*:?\s*', text, re.I):
            requirement_lead = True
        if (requirement_section is not None or requirement_lead) and not requirement_header:
            row_policy = {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}
            normative_row = True
''')
    text = replace(text, "        if heading and function_section is None and document_component_policy(text) is None:\n", "        if requirement_header:\n            continue\n        if heading and not normative_row and function_section is None and (document_component_policy(text) is None or re.search(r'(?:design|architecture|architektur|übersicht|overview)\\s*$', structural, re.I)):\n")
    text = replace(text, "            policy = document_component_policy(clause)\n", "            policy = row_policy if normative_row else document_component_policy(clause)\n")
    text = replace(text, "policy['kind'] in {'CATEGORY', 'INSTANCE', 'REQUIREMENT'}", "policy['kind'] in {'CATEGORY', 'INSTANCE', 'REQUIREMENT', 'FUNCTION'} and not re.fullmatch(r'(?:Schnittstellen|Interfaces|Anschlüsse)\\s*:', text, re.I)")
    anchor = "    in_section = False\n    ignored = False\n"
    text = replace(text, anchor, anchor + "    aliases = {name.casefold() for name in document_device_aliases(scope_prefix + ''.join(row['text'] for row in rows))}\n")
    text = replace(text, "        if not content:\n            continue\n        protected = set()\n", r'''        if not content:
            continue
        # A functional partner ("CDC (Lenk-/Bremsanforderungen)") is not a
        # physical interface. Keep ADC usable when explicitly named as a port.
        partner = re.fullmatch(r'([A-Z][A-Z0-9_-]{1,15})\s*\(([^)]+)\)\s*\.?', content)
        if partner and partner[1].casefold() in aliases:
            continue
        links = re.fullmatch(r'(?:Direkte?\s+|Direct\s+)?(?:Sensorlinks?|sensor links?|Anschlüsse|Interfaces)\s*\(([^)]+)\)\s*\.?', content, re.I)
        if links:
            content = links[1]
        if document_qualified_transports(content, profiles):
            content = re.sub(_DOCUMENT_TRANSPORT_QUALIFIER, '', content, flags=re.I)
        protected = set()
''')
    text = replace(text, "            name = match.group()\n", r'''            name = match.group()
            # Unknown technology labels may have descriptive suffixes, but
            # ordinary connection prose does not introduce a new protocol.
            if name.casefold() in aliases or re.match(r'^(?:Verbindung(?:en)?|connections?)\s+(?:zum|zur|zu|mit|to|with)\b', piece, re.I):
                continue
            if re.fullmatch(r'[\w\u2010\u2011\u2012\u2013\u2014\u2212-]*(?:Signale|Nachrichten|Signals|Messages)\s*(?:\([^)]*\))?', piece, re.I):
                continue
''')
    text = replace(text, "if not piece or any(document_registered_transport_citation(p['id'], piece, profiles=profiles) for p in candidates):", "if not piece or any(document_registered_transport_citation(p['id'], piece, profiles=profiles) for p in profiles):")
    return text


stage('backend/nis/agent/orchestration/project_intake.py', parser)
stage('backend/nis/communication/registry.py', lambda text: replace(text,
    '    token = str(value or "custom_protocol").strip().lower().replace("-", "_").replace("/", "_").replace(" ", "_")',
    '    value = str(value or "custom_protocol").translate(str.maketrans({char: "-" for char in "\\u2010\\u2011\\u2012\\u2013\\u2014\\u2212"}))\n    token = value.strip().lower().replace("-", "_").replace("/", "_").replace(" ", "_")'))
