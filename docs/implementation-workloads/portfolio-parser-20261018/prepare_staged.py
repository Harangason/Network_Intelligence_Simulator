"""Prepare a reviewable repair outside frozen application/release inputs."""
from pathlib import Path
import difflib
import hashlib
import json
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
FILES = ['backend/nis/agent/orchestration/project_intake.py',
         'frontend/src/features/agent/lib/document-clarification.ts']


def main():
    before = {}
    for relative in FILES:
        original = ROOT / relative
        before[relative] = hashlib.sha256(original.read_bytes()).hexdigest()
        target = OUT / 'before' / relative
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != before[relative]:
            raise RuntimeError('Historical preparation refuses to replace the original baseline: ' + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)

    def replace_once(text, old, new):
        if text.count(old) != 1:
            raise ValueError('Staging input changed: ' + old[:90])
        return text.replace(old, new, 1)

    source = (ROOT / FILES[0]).read_text(encoding='utf-8')
    source = replace_once(source,
        "    # Bare architecture services describe logical responsibilities.",
        "    # Design instructions constrain an architecture; their comma-separated\n"
        "    # object lists are not an installed hardware inventory.\n"
        "    if re.match(r'^(?:Die|The)\\s+(?:Architektur|architecture)\\b.*\\b(?:wird|werden|shall|must|is)\\b|^(?:Jede[rsnm]?|Each|Every)\\s+(?:Funktion|Function|Schnittstelle|Interface)\\b', text, re.I):\n"
        "        return {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}\n"
        "    # Bare architecture services describe logical responsibilities.")
    # Extend the existing semantic captions; none of these identify a source file,
    # industry profile, named participant or particular project.
    source = source.replace('Systemfunktionen|Funktionsbeschreibung',
                            'Systemfunktionen|Kernfunktionen|Core functions|Funktionsbeschreibung')
    scope_pattern = (
        r'(?:Mechanische|Elektrische|Elektronische|Physische|Logische|Mechanical|Electrical|Electronic|Physical|Logical)'
        r'(?:[, /-]+(?:und|and|E/E|mechanische|elektrische|elektronische|physische|logische|mechanical|electrical|electronic|physical|logical))*'
        r'[- ]+(?:Architektur|Architecture)|(?:Regulatorische|Funktionale|Nichtfunktionale|Technische|Regulatory|Functional|Nonfunctional|Technical)'
        r'\s+(?:Anforderungen|Requirements)|(?:Zweck|Purpose)(?:\s+(?:und|and)\s+(?:Systemgrenze|Systemübersicht|System boundary|System overview))?'
        r'|Produkt- und Einsatzprofil|Product and operating profile|Kernfunktionen|Core functions'
        r'|Schnittstellen und Datenobjekte|Interfaces and data objects|Betriebsmodi und Degradation|Operating modes and degradation'
        r'|Ergebnisartefakte|Result artifacts|ADAS-, Automatisierungs- und Wahrnehmungsumfang'
        r'|(?:Safety|Security|Sicherheit|SOTIF|KI-Sicherheit|Cybersecurity|Qualität|Quality|Compliance)'
        r'(?:\s*(?:,|/|&|und|and)\s*(?:Safety|Security|Sicherheit|SOTIF|KI-Sicherheit|Cybersecurity|Qualität|Quality|Compliance|Betrieb|Operations?))*'
    )
    # The existing scope helper remains the single backend resolution path.
    source = replace_once(source,
        "        if re.fullmatch(_DOCUMENT_GENERIC_SYSTEM_CHAPTER, title, re.I):",
        f"        if re.fullmatch(_DOCUMENT_GENERIC_SYSTEM_CHAPTER, title, re.I) or re.fullmatch({scope_pattern!r}, title, re.I):")
    source = replace_once(source,
        "        if heading and re.fullmatch(r'(?:Architektur|Architecture|Hardware(?:komponenten| components)?)\\s*:?\\s*', structural, re.I):",
        "        if heading and (re.fullmatch(r'(?:Architektur|Architecture|Hardware(?:komponenten| components)?)\\s*:?\\s*', structural, re.I)\n"
        "                        or re.fullmatch(r'(?:Mechanische|Elektrische|Elektronische|Physische|Logische|Mechanical|Electrical|Electronic|Physical|Logical)(?:[, /-]+(?:und|and|E/E|mechanische|elektrische|elektronische|physische|logische|mechanical|electrical|electronic|physical|logical))*[- ]+(?:Architektur|Architecture)', structural, re.I)):")
    source = replace_once(source,
        "        requirement_header = re.fullmatch(r'(?:(?:Referenz[- ]?)?Anforderungen|(?:Reference )?Requirements)\\s*:?\\s*', structural, re.I)",
        "        requirement_header = re.fullmatch(r'(?:(?:(?:Referenz[- ]?|Regulatorische |Funktionale |Nichtfunktionale |Technische ))?Anforderungen|(?:(?:Reference|Regulatory|Functional|Nonfunctional|Technical) )?Requirements)\\s*:?\\s*', structural, re.I)")
    source = replace_once(source,
        "        assurance_header = re.fullmatch(r'(?:Safety|Security|Sicherheit)(?:\\s*(?:,|/|&|und|and)\\s*(?:Safety|Security|Sicherheit|Qualität|Quality|Betrieb|Operations?))*\\s*:?\\s*', structural, re.I)",
        "        assurance_header = re.fullmatch(r'(?:Safety|Security|Sicherheit|SOTIF|KI-Sicherheit|Cybersecurity)(?:\\s*(?:,|/|&|und|and)\\s*(?:Safety|Security|Sicherheit|SOTIF|KI-Sicherheit|Cybersecurity|Compliance|Qualität|Quality|Betrieb|Operations?))*\\s*:?\\s*', structural, re.I)")
    source = replace_once(source, '    heading_sequence = 0\n', '    heading_sequence = 0\n    function_table = False\n')
    source = replace_once(source,
        "        if heading and architecture_section is not None",
        "        if heading:\n            function_table = False\n"
        "        if text.startswith('|'):\n"
        "            cells = [cell.strip().strip('*') for cell in text.strip('|').split('|')]\n"
        "            if any(re.fullmatch(r'Funktionsgruppe|Funktion|Function group|Function', cell, re.I) for cell in cells):\n"
        "                function_table = True\n                continue\n"
        "            if function_table and all(re.fullmatch(r'[: -]+', cell) for cell in cells):\n                continue\n"
        "            if function_table:\n"
        "                row_policy = {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}\n"
        "        else:\n            function_table = False\n"
        "        if heading and architecture_section is not None")
    source = replace_once(source,
        "            policy = row_policy if normative_row else document_component_policy(clause)",
        "            policy = row_policy if normative_row or function_table else document_component_policy(clause)")
    source = replace_once(source,
        "        split = len(clauses) > 1 and not normative_row and",
        "        split = len(clauses) > 1 and not normative_row and not function_table and")
    source = replace_once(source,
        "            required = bool(architecture_section is not None or split or in_functions",
        "            required = bool(function_table or architecture_section is not None or split or in_functions")

    frontend = (ROOT / FILES[1]).read_text(encoding='utf-8')
    frontend = frontend.replace('Systemfunktionen|Funktionsbeschreibung',
                                'Systemfunktionen|Kernfunktionen|Core functions|Funktionsbeschreibung')
    frontend = replace_once(frontend,
        "    return /^(?:Systemstruktur",
        '    if (new RegExp(' + json.dumps('^(?:' + scope_pattern + ')$', ensure_ascii=False) + ', "iu").test(title)) return true;\n'
        "    return /^(?:Systemstruktur")
    changes = []
    for relative, edited in zip(FILES, [source, frontend]):
        target = OUT / 'staged' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(edited, encoding='utf-8')
        changes.extend(difflib.unified_diff((ROOT / relative).read_text(encoding='utf-8').splitlines(True),
                                          edited.splitlines(True), fromfile='before/' + relative,
                                          tofile='staged/' + relative))
    (OUT / 'proposed-repair.diff').write_text(''.join(changes), encoding='utf-8')
    (OUT / 'source-baseline.json').write_text(json.dumps(before, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'staged_only': True, 'canonical_files_unchanged':
                     all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value for name, value in before.items()),
                     'files': FILES}))


if __name__ == '__main__':
    main()
