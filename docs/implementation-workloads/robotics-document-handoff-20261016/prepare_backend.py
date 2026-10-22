"""Prepare additional Markdown semantics in an isolated workload copy."""
from pathlib import Path

OUT = Path(__file__).parent
TARGET = OUT / 'staged/backend/nis/agent/orchestration/project_intake.py'
text = (OUT / 'before/backend/nis/agent/orchestration/project_intake.py').read_text(encoding='utf-8')


def replace(old, new, count=1):
    global text
    assert text.count(old) == count, (old[:100], text.count(old))
    text = text.replace(old, new)


replace("    source_quote: str = Field(min_length=1, max_length=1200)\n\n\nclass DocumentTechnology", "    source_quote: str = Field(min_length=1, max_length=1200)\n    source_context: list[str] = Field(default_factory=list, max_length=6)\n\n\nclass DocumentTechnology")
replace("    component_references = {row['source_ref']: row['text'].strip() for row in document_component_sources(rows, scope_prefix=scope_prefix)}", "    component_units = {row['source_ref']: row for row in document_component_sources(rows, scope_prefix=scope_prefix)}\n    component_references = {key: row['text'].strip() for key, row in component_units.items()}")
replace("if 'source_quote' in item or (field == 'components' and 'name' in item):", "if 'source_quote' in item or (field == 'components' and ('name' in item or 'source_context' in item)):")
replace("            item['source_quote'] = selected[reference]\n", "            item['source_quote'] = selected[reference]\n            if field == 'components':\n                item['source_context'] = component_units[reference].get('source_context', [])\n")
replace("    function_section = None\n    first_function_body = False\n    excluded_section = None\n    requirement_section = None\n    requirement_lead = False\n", "    function_section = None\n    first_function_body = False\n    excluded_section = None\n    requirement_section = None\n    requirement_lead = False\n    architecture_section = None\n    interface_section = None\n    markdown_path = []\n    heading_sequence = 0\n")
replace("        heading = re.match(r'^(\\d+(?:\\.\\d+)*)[.)]?\\s+(.+)', text)\n        structural = heading[2] if heading else text\n        requirement_header = re.fullmatch(r'(?:Anforderungen|Requirements)\\s*:?\\s*', structural, re.I)", """        markdown = re.match(r'^(#{1,6})\\s+(.+?)(?:\\s+#+)?$', text)
        logical = markdown[2] if markdown else text
        heading = re.match(r'^(\\d+(?:\\.\\d+)*)[.)]?\\s+(.+)', logical)
        structural = heading[2] if heading else logical
        if markdown:
            level = len(markdown[1])
            markdown_path = [entry for entry in markdown_path if entry[0] < level]
            heading_sequence += 1
            markdown_path.append((level, logical, str(heading_sequence)))
            heading = {1: '.'.join(entry[2] for entry in markdown_path), 2: structural}
        if heading and architecture_section is not None and not heading[1].startswith(architecture_section + '.'):
            architecture_section = None
        if heading and re.fullmatch(r'(?:Architektur|Architecture|Hardware(?:komponenten| components)?)\\s*:?\\s*', structural, re.I):
            architecture_section = heading[1]
        if heading and interface_section is not None and not heading[1].startswith(interface_section + '.'):
            interface_section = None
        if heading and re.match(r'^(?:Schnittstellen|Interfaces|Anschl\u00fcsse|Connections)\\b', structural, re.I):
            interface_section = heading[1]
        requirement_header = re.fullmatch(r'(?:(?:Referenz[- ]?)?Anforderungen|(?:Reference )?Requirements)\\s*:?\\s*', structural, re.I)""")
replace("        if re.match(r'^(?:Testfälle|Test cases|Erweiterungen|Erweiterungsmöglichkeiten|Extensions|Software[- ]?Schnittstellen|Software interfaces|ROS2 Topics|Services)\\b', structural, re.I):", "        if re.match(r'^(?:Index|Inhaltsverzeichnis|Contents|Table of contents|Testfälle|Test cases|Verifikation|Verification|Varianten|Variants|Erweiterungen|Erweiterungsmöglichkeiten|Extensions|Systemkontext|System context|Zweck|Purpose|Betriebsmodi|Operating modes|(?:Safety|Security|Sicherheit)(?=\\s*:?\\s*$)|Software[- ]?Schnittstellen|Software interfaces|ROS2 Topics|Services)\\b', structural, re.I):")
replace("    first_function_body = False\n    excluded_section = None\n", "    first_function_body = False\n    excluded_section = None\n    excluded_normative = False\n")
replace("            excluded_section = heading[1] if heading else ''\n", "            excluded_section = heading[1] if heading else ''\n            excluded_normative = bool(re.match(r'^(?:Index|Inhaltsverzeichnis|Contents|Table of contents|Testfälle|Test cases|Verifikation|Verification)\\b', structural, re.I))\n")
replace("        if not normative_row and (excluded_section is not None or text.startswith('/')):\n            continue", "        if (excluded_section is not None and (not normative_row or excluded_normative)) or text.startswith('/') or re.match(r'^\\s*[-*]?\\s*\\*{0,2}TC[-_]', text, re.I):\n            continue")
replace("Funktionen|Functions|Aufgaben|Responsibilities)\\s*:?\\s*$', text, re.I)", "Funktionen|Functions|Aufgaben|Responsibilities)\\s*:?\\s*$', logical, re.I)")
replace("        if row['source_ref'].startswith('CTX-'):\n            continue\n", "        if row['source_ref'].startswith('CTX-'):\n            continue\n        # Markdown headings and two-column numbered index rows navigate the\n        # document; they do not declare additional installed hardware.\n        if markdown or re.match(r'^\\|\\s*\\d+\\s*\\|[^|]+\\|\\s*$', text):\n            continue\n")
replace("        if requirement_header:\n            continue\n", "        if requirement_header or re.match(r'^- (?:Aufgaben-Anlage|Architektur-Evidence):', text):\n            continue\n        if markdown_path and row_policy is None and architecture_section is None and function_section is None:\n            continue  # Unclassified document prose is not a component declaration.\n")
replace("        if not normative_row and re.match(r'^(?:Beispiel", "        if interface_section is not None and not normative_row:\n            if re.search(r'\\b(?:jede|each)\\b', text, re.I):\n                row_policy = {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}\n                normative_row = True\n            else:\n                continue  # Transport declarations remain technology facts, not hardware.\n        if not normative_row and re.match(r'^(?:Beispiel")
replace("            elif char in ',;' and depth == 0:\n                clauses.append(body[start:index].strip().rstrip('.'))\n                start = index + 1", "            elif depth == 0 and (char in ',;' or (architecture_section is not None and char == '/' and index > 0 and index + 1 < len(body) and body[index - 1] != '-' and body[index + 1] != '-')):\n                clauses.append(body[start:index].strip().rstrip('.'))\n                start = index + 1\n            elif depth == 0 and architecture_section is not None and not body[:index].rstrip().endswith('-') and re.match(r' (?:und|and) ', body[index:]):\n                delimiter = re.match(r' (?:und|and) ', body[index:])[0]\n                clauses.append(body[start:index].strip().rstrip('.'))\n                start = index + len(delimiter)")
# Preserve the literal noun classes; quantities still require explicit evidence.
replace("(?:SPS|DCS|PLC|ECU)\\b", "(?:SPS|DCS|SIS|PLC|CNC|ECU|HMI|BMS)\\b", count=1)
replace("Greifer|Greifarm|[\\w-]*motor", "Greifer|Greifarm|Endeffektor|[\\w-]*motor", count=1)
replace("(?:LiDAR|Radar|Kamera|IMU|Encoder)\\b", "(?:LiDAR|Radar|Kameras?|IMU|Encoder|Scanner|Waagen?|Messtaster)\\b", count=1)
replace("        split = len(clauses) > 1 and (prefix or (mixed_hardware and not re.search(r'Funktion|Function|Anforderung|REQ|Testf', text, re.I)))", "        split = len(clauses) > 1 and not normative_row and (prefix or architecture_section is not None or (mixed_hardware and not re.search(r'Funktion|Function|Anforderung|REQ|Testf', text, re.I)))")
replace("            required = bool(split or in_functions", "            required = bool(architecture_section is not None or split or in_functions")
replace("                           'text': clause, 'policy': policy, 'required': required,", "                           'text': clause, 'policy': policy, 'required': required,\n                           'source_context': [entry[1] for entry in markdown_path],")
replace("        removed = {'source_quote', 'name'} if definition == 'DocumentComponent' else {'source_quote'}", "        removed = {'source_quote', 'name', 'source_context'} if definition == 'DocumentComponent' else {'source_quote'}")
# The context is assigned from source structure, never supplied by the model.
replace("    for component in result.components:\n        policy = document_component_policy(component.source_quote)", """    # Citation grouping may differ at a window boundary. Bind the context to
    # original character positions rather than to a particular grouping.
    from bisect import bisect_right
    context_offsets, context_values, context_path = [0], [[]], []
    offset = 0
    for line in (scope_prefix + source).splitlines(keepends=True):
        header = re.match(r'^(#{1,6})\\s+(.+?)(?:\\s+#+)?$', line.strip())
        offset += len(line)
        if header:
            level = len(header[1])
            context_path = [entry for entry in context_path if entry[0] < level]
            context_path.append((level, header[2]))
            context_offsets.append(offset)
            context_values.append([entry[1] for entry in context_path])
    context_cache = {}
    for component in result.components:
        if component.source_quote not in context_cache:
            contexts = []
            position = source.find(component.source_quote)
            while position >= 0:
                contexts.append(context_values[bisect_right(context_offsets, len(scope_prefix) + position) - 1])
                position = source.find(component.source_quote, position + 1)
            context_cache[component.source_quote] = contexts
        contexts = context_cache[component.source_quote]
        if component.source_context and component.source_context not in contexts:
            semantic_errors.append(f'{component.name}: unbelegter Abschnittskontext.')
        if any(contexts) and component.source_context not in contexts:
            semantic_errors.append(f'{component.name}: Abschnittskontext fehlt oder ist veraltet.')
        policy = document_component_policy(component.source_quote)""")
TARGET.write_text(text, encoding='utf-8')
print('Staged backend prepared; live application source untouched.')
