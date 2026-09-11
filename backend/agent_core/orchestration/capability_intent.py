"""Read-only product questions must not resume an unrelated pending workload."""
import re


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
