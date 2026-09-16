"""Read-only product questions must not resume an unrelated pending workload."""
import re


def connectivity_question(prompt):
    match = re.fullmatch(r'\s*(?:wie sind|how are)\s+(.+?)\s+(?:und|and)\s+(.+?)\s+(?:aktuell\s+|currently\s+)?(?:angebunden|verbunden|connected)\s*[?.!]?\s*', prompt, re.I)
    return tuple(part.strip(' \"') for part in match.groups()) if match else None


def communication_question(prompt):
    match = re.fullmatch(r'\s*(?:Prüfe die bestehende Architektur und stelle fest, ob|Kann)\s+([\w.-]+)\s+mit\s+([\w.-]+)\s+kommunizieren(?: kann)?[?.!]?\s*', prompt, re.I)
    return match.groups() if match else None


def signal_inspection(prompt):
    if not re.match(r'\s*(?:bitte\s+)?(?:prüf\w*|pruef\w*|validier\w*|check|validate|inspect)\b', prompt, re.I):
        return None
    match = re.search(r'\b(?:signal|signals)\s+(?:namens\s+)?[\"„]?([\w.-]+)', prompt, re.I)
    if match and not re.fullmatch(r'prüfen|pruefen|check|validate', match[1], re.I):
        return match[1].strip('.')
    match = re.match(r'\s*(?:prüfe|pruefe|validate|check)\s+([\w.-]+)\s*:', prompt, re.I)
    return match[1] if match and re.search(r'\brpm\b|\bbit\b|Auflösung|Encoding', prompt, re.I) else None


def finding_assessment(prompt):
    match = re.fullmatch(r'\s*(?i:bewerte|assess)\s+([A-Z][A-Z_]+)\s+(?:am|an|at|on)\s+([\w.-]+?)\s*[.!]?\s*', prompt)
    return match.groups() if match else None


def connection_request(prompt):
    # A following imperative belongs to the goal, never to the target name.
    # Only split at an explicit clause boundary, preserving compound names.
    text = re.split(r'(?:\s*[,;]\s*|\s+(?:und|and|then|anschließend)\s+)(?:prüfe\w*|pruefe\w*|check|validate|simuliere\w*|simulate|analysiere\w*|analyze)\b', prompt, maxsplit=1, flags=re.I)[0]
    match = re.fullmatch(r'\s*(?:bitte\s+)?(?:verbinde|connect)\s+(?:die\s+Funktion\s+)?(.+?)\s+(?:mit|with)\s+(?:der\s+Funktion\s+)?(.+?)\s*[.!]?\s*', text, re.I)
    return tuple(value.strip(' .!"') for value in match.groups()) if match else None


def capability_question(prompt: str) -> str | None:
    if len(prompt) > 1200:
        return None
    text = prompt.casefold().strip()
    if re.search(r'\b(?:in welchem|welches|in which)\s+projekt|which project', text):
        return '@project'
    inquiry = re.match(r'^(?:du\s+)?(?:kennst|kennt|was|welche|wie|zeige|zeig|erkläre|erkl[aä]r|kannst|wo|tell|show|what|how|do you)\b', text)
    if not inquiry:
        return None
    if re.search(r'reparatur.?agent|repair agent', text) and not re.search(r'\b(?:reparier\w*|übernimm|stelle.*wieder her|implementier\w*)\b', text):
        return 'repair'
    if re.search(r'f[aä]higkeiten|faehigkeiten|capabilities|was kannst du|welche.*agent|welche.*wizard|alle.*wizard|welche.*abl[aä]uf', text):
        return ''
    if re.search(r'wizard|assistent|agent', text):
        for pattern, key in [('signal', 'signal'), ('nachricht|message', 'message'), ('struktur|transfer', 'structure'),
                             ('funktion', 'function'), ('routing', 'routing'), ('simulation', 'simulation'),
                             ('engineering|projekt', 'project'), ('intelligence', 'intelligence')]:
            if re.search(pattern, text):
                return key
    return None
