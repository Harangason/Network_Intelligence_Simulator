"""Consolidate the proposed chapter rules in the existing vocabulary owner."""
from pathlib import Path
import difflib
import importlib.util
import json
import re
import shutil
import sys
import ast

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BACKEND = 'backend/nis/agent/orchestration/project_intake.py'
FRONTEND = 'frontend/src/features/agent/lib/document-clarification.ts'
VOCAB = 'backend/nis/domain/inventory-vocabulary.json'
PROJECTION = 'frontend/src/features/agent/lib/inventory-vocabulary.json'
sys.path.insert(0, str(ROOT))
_before_tree = ast.parse((OUT / 'before' / BACKEND).read_text(encoding='utf-8'))
_DOCUMENT_GENERIC_SYSTEM_CHAPTER = next(ast.literal_eval(node.value) for node in _before_tree.body
    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == '_DOCUMENT_GENERIC_SYSTEM_CHAPTER' for target in node.targets))


def once(source, old, new):
    assert source.count(old) == 1, old[:100]
    return source.replace(old, new, 1)


def main():
    vocabulary = json.loads((OUT / 'before' / VOCAB).read_text(encoding='utf-8'))
    architecture = (r'(?:Architektur|Architecture|Hardware(?:komponenten| components)?|'
                    r'(?:Mechanische|Elektrische|Elektronische|Physische|Logische|Mechanical|Electrical|Electronic|Physical|Logical)'
                    r'(?:[, /-]+(?:und|and|E/E|mechanische|elektrische|elektronische|physische|logische|mechanical|electrical|electronic|physical|logical))*'
                    r'[- ]+(?:Architektur|Architecture))')
    functions = r'(?:Systemfunktionen|Kernfunktionen|Core functions|Funktionsbeschreibung|Functional description|Funktionen|Functions|Aufgaben|Responsibilities)'
    requirements = (r'(?:(?:(?:Referenz[- ]?|Regulatorische |Funktionale |Nichtfunktionale |Technische ))?Anforderungen|'
                    r'(?:(?:Reference|Regulatory|Functional|Nonfunctional|Technical) )?Requirements)')
    assurance = (r'(?:Safety|Security|Sicherheit|SOTIF|KI-Sicherheit|Cybersecurity)'
                 r'(?:\s*(?:,|/|&|und|and)\s*(?:Safety|Security|Sicherheit|SOTIF|KI-Sicherheit|Cybersecurity|Compliance|Qualität|Quality|Betrieb|Operations?))*')
    interfaces = r'(?:Schnittstellen|Interfaces|Anschlüsse|Connections)(?:\s+(?:und|and)\s+(?:Daten(?:objekte)?|[Dd]ata(?: objects)?))?'
    overview = r'(?:Übersicht|Overview|Systemübersicht|System overview)'
    generic = (r'(?:' + _DOCUMENT_GENERIC_SYSTEM_CHAPTER + r'|(?:Zweck|Purpose)(?:\s+(?:und|and)\s+(?:Systemgrenze|Systemübersicht|System boundary|System overview))?'
               r'|Produkt- und Einsatzprofil|Product and operating profile|Betriebsmodi und Degradation|Operating modes and degradation'
               r'|Ergebnisartefakte|Result artifacts|(?:[\w/,-]+\s+)*(?:Wahrnehmungsumfang|Automatisierungsumfang|Funktionsumfang)'
               r'|Systemstruktur(?:\s*\(Top-Level-Architektur\))?|System structure(?:\s*\(Top-Level Architecture\))?'
               r'|Systemgrenzen(?: und Systemkontext)?|System boundaries(?: and System context)?|Systemkontext|System context'
               r'|Zielbild der (?:E/E[- ]?)?Architektur|Architecture (?:vision|target)|Target architecture|Domain[- ]Controller[- ]Design|Controller[- ]Design'
               r'|(?:Elektronische|Elektrische|Mechanische|Software)\s*Domäne|(?:Electronic|Electrical|Mechanical|Software) domain)')
    vocabulary['document_chapters'] = {'architecture': architecture, 'functions': functions,
                                      'requirements': requirements, 'assurance': assurance,
                                      'interfaces': interfaces, 'overview': overview, 'generic': generic}
    # Grammatical German dative and English plural are the same existing role.
    vocabulary['roles']['ecus']['nouns'] = vocabulary['roles']['ecus']['nouns'].replace('controllers?', 'controller(?:s|n)?')
    vocabulary['roles']['ecus']['generic'] = vocabulary['roles']['ecus']['generic'].replace('controllers?', 'controller(?:s|n)?')
    for relative in (VOCAB, PROJECTION):
        before = OUT / 'before' / relative
        before.parent.mkdir(parents=True, exist_ok=True)
        if not before.exists():
            raise RuntimeError('Original baseline must already exist: ' + relative)
        target = OUT / 'staged' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(vocabulary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    source = (OUT / 'before' / BACKEND).read_text(encoding='utf-8')
    source = once(source, 'import re\n', 'import re\nimport unicodedata\n\nfrom backend.nis.agent.tools.inventory_quantities import VOCABULARY, quantities\n')
    source = once(source, 'def document_source_scope(context: list[str]) -> list[str]:',
                  "def document_chapter_kind(caption: str) -> str | None:\n"
                  "    \"\"\"Resolve semantic chapters through the shared source vocabulary.\"\"\"\n"
                  "    title = re.sub(r'[\\u2010-\\u2015\\u2212]', '-', unicodedata.normalize('NFKC', caption))\n"
                  "    title = re.sub(r'^\\d+(?:\\.\\d+)*[.)]?\\s+', '', title).rstrip(':').strip()\n"
                  "    return next((kind for kind, pattern in VOCABULARY['document_chapters'].items()\n"
                  "                 if re.fullmatch(pattern, title, re.I)), None)\n\n\n"
                  'def document_source_scope(context: list[str]) -> list[str]:')
    start = source.index('    label = re.sub(', source.index('def document_source_scope'))
    end = source.index('    return context[:]', start)
    source = source[:start] + "    if document_chapter_kind(context[-1]) in {'architecture', 'functions', 'requirements', 'interfaces', 'overview'}:\n        return context[:-1]\n" + source[end:]
    start = source.index('_DOCUMENT_GENERIC_SYSTEM_CHAPTER = ')
    end = source.index('def document_component_sources', start)
    source = source[:start] + ('def document_system_scope(context: list[str]) -> list[str]:\n'
                              '    """Keep named systems while crossing shared semantic chapters."""\n'
                              '    for index, caption in enumerate(context):\n'
                              '        if document_chapter_kind(caption):\n'
                              '            return context[:index]\n'
                              '    return context[:]\n\n\n') + source[end:]
    source = once(source, '    # Bare architecture services describe logical responsibilities.',
                  "    # Method requirements describe how to model a system, not its installed inventory.\n"
                  "    if re.match(r'^(?:Die Architektur wird (?:mindestens )?in\\b.*\\bzerlegt|The architecture (?:is to be|shall be) decomposed\\b)|^(?:Jede[rsnm]?|Each|Every)\\s+(?:Funktion|Function|Schnittstelle|Interface)\\b.*\\b(?:wird|werden|must|shall|is to be)\\b', text, re.I):\n"
                  "        return {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}\n"
                  '    # Bare architecture services describe logical responsibilities.')
    source = source.replace('(?:controller|computer|rechner|steuergerät|steuerung|server|workstation)\\b',
                            '(?:controller|computer|rechner|steuergerät|steuerung|server|workstation)(?:s|n|en)?\\b')
    source = once(source, '    heading_sequence = 0\n', '    heading_sequence = 0\n    function_table = False\n')
    source = once(source, "        structural = heading[2] if heading else logical\n",
                  "        structural = heading[2] if heading else logical\n        chapter = document_chapter_kind(structural)\n")
    source = once(source, "        if heading and architecture_section is not None",
                  "        if heading:\n            function_table = False\n"
                  "        if text.startswith('|'):\n"
                  "            cells = [cell.strip().strip('*') for cell in text.strip('|').split('|')]\n"
                  "            if any(re.fullmatch(r'Funktionsgruppe|Funktion|Function group|Function', cell, re.I) for cell in cells):\n"
                  "                function_table = True\n                continue\n"
                  "            if function_table and all(re.fullmatch(r'[: -]+', cell) for cell in cells):\n                continue\n"
                  "            if function_table and not normative_row:\n"
                  "                row_policy = {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}\n"
                  "        else:\n            function_table = False\n"
                  "        if heading and architecture_section is not None")
    for name, kind in [('assurance_header', 'assurance'), ('requirement_header', 'requirements')]:
        pattern = r'^        ' + name + r' = .+$'
        source, count = re.subn(pattern, '        ' + name + " = chapter == '" + kind + "'", source, flags=re.M)
        assert count == 1
    source, count = re.subn(r'^        if heading and re.fullmatch\(.+structural, re.I\):$',
                            "        if heading and chapter == 'architecture':", source, count=1, flags=re.M)
    assert count == 1
    source, count = re.subn(r'^        function_header = .+$', "        function_header = chapter == 'functions'", source, flags=re.M)
    assert count == 1
    source = source.replace('Systemfunktionen|Funktionsbeschreibung', 'Systemfunktionen|Kernfunktionen|Core functions|Funktionsbeschreibung')
    source = once(source,
                  "        if not normative_row and re.match(r'^(?:Der|Die|Das|Es|The)\\b', text, re.I) and re.search(r'\\b(?:ist|sind|nutzt|beschreibt|besteht|uses|is|are)\\b', text, re.I):",
                  "        if not normative_row and not any(quantities(text).values()) and re.match(r'^(?:Der|Die|Das|Es|The)\\b', text, re.I) and re.search(r'\\b(?:ist|sind|nutzt|beschreibt|besteht|uses|is|are)\\b', text, re.I):")
    source = once(source,
                  "        prefix = re.match(r'^\\s*(?:Architektur|Architecture|Hardwarekomponenten|Hardware components)\\s*:\\s*', text, re.I)",
                  "        prefix = re.match(r'^\\s*(?:(?:Architektur|Architecture|Hardwarekomponenten|Hardware components)\\s*:\\s*|(?:Die Architektur (?:wird aus|besteht aus)|The architecture (?:is composed of|consists of))\\s+)', text, re.I)")
    source = source.replace("elif depth == 0 and architecture_section is not None and not body[:index]", "elif depth == 0 and (architecture_section is not None or prefix) and not body[:index]")
    source = once(source, "        split = len(clauses) > 1 and not normative_row and", "        split = len(clauses) > 1 and not normative_row and not function_table and")
    source = once(source, "            policy = row_policy if normative_row else document_component_policy(clause)",
                  "            policy = row_policy if normative_row or function_table else document_component_policy(clause)")
    source = once(source, "            required = bool(architecture_section is not None or split or in_functions", "            required = bool(function_table or architecture_section is not None or split or in_functions")

    frontend = (OUT / 'before' / FRONTEND).read_text(encoding='utf-8')
    frontend = "import inventoryVocabulary from './inventory-vocabulary.json' with { type: 'json' };\n" + frontend
    start = frontend.index('export function documentSourceScope(')
    end = frontend.index('\nfunction sameDocumentSystem', start)
    frontend = frontend[:start] + (
        "function documentChapterKind(caption: string) {\n"
        "  const title = caption.normalize('NFKC').replace(/[\\u2010-\\u2015\\u2212]/g, '-').replace(/^\\d+(?:\\.\\d+)*[.)]?\\s+/u, '').replace(/:\\s*$/u, '').trim();\n"
        "  return Object.entries(inventoryVocabulary.document_chapters).find(([, pattern]) => new RegExp(`^(?:${pattern})$`, 'iu').test(title))?.[0];\n"
        "}\n\nexport function documentSourceScope(context: string[]) {\n"
        "  if (!context.length) return [];\n"
        "  return ['architecture', 'functions', 'requirements', 'interfaces', 'overview'].includes(documentChapterKind(context.at(-1)!) ?? '') ? context.slice(0, -1) : [...context];\n"
        "}\n\nexport function documentSystemScope(context: string[]) {\n"
        "  const index = context.findIndex(label => documentChapterKind(label) !== undefined);\n"
        "  return index < 0 ? [...context] : context.slice(0, index);\n"
        "}\n") + frontend[end:]
    for relative, edited in [(BACKEND, source), (FRONTEND, frontend)]:
        (OUT / 'staged' / relative).write_text(edited, encoding='utf-8')
    differences = []
    for relative in (BACKEND, FRONTEND, VOCAB, PROJECTION):
        differences.extend(difflib.unified_diff((OUT / 'before' / relative).read_text(encoding='utf-8').splitlines(True),
                           (OUT / 'staged' / relative).read_text(encoding='utf-8').splitlines(True), fromfile='before/' + relative,
                           tofile='staged/' + relative))
    (OUT / 'proposed-repair.diff').write_text(''.join(differences), encoding='utf-8')
    print('Refined staging only; four canonical application files unchanged.')


if __name__ == '__main__':
    main()
