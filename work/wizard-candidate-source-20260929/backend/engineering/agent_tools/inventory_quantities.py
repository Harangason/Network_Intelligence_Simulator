"""Shared browser/chat hardware vocabulary; quantities do not establish ports."""
import json
from pathlib import Path
import re

VOCABULARY = json.loads((Path(__file__).resolve().parents[3] /
    'frontend/src/lib/agent/inventory-vocabulary.json').read_text(encoding='utf8'))
WORDS = {'ein': 1, 'eine': 1, 'einen': 1, 'einem': 1, 'einer': 1, 'eins': 1,
         'zwei': 2, 'drei': 3, 'vier': 4, 'fuenf': 5, 'funf': 5, 'sechs': 6,
         'sieben': 7, 'acht': 8, 'neun': 9, 'zehn': 10}
NUMBER = r'(\d+|' + '|'.join(WORDS) + ')'


def quantities(text):
    result = {}
    for role, rule in VOCABULARY['roles'].items():
        pattern = re.compile(r'\b' + NUMBER + r'\s+((?:(?:' + VOCABULARY['modifiers'] +
                             r')\s+){0,3}(?:' + rule['nouns'] + r'))\b')
        groups, declared = {}, 0
        for raw in text.splitlines():
            line = re.sub(r'^\s*\d+[.)]\s+', '', raw.lower())
            line = re.sub(r'([a-zäöü]+)-/([a-zäöü]+)', r'\1\2', line)
            for a, b in [('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')]:
                line = line.replace(a, b)
            line = re.sub(r'[^a-z0-9]+', ' ', line).strip()
            for match in pattern.finditer(line):
                prefix = line[:match.start()].split()[-3:]
                if any(word in {'kein', 'keine', 'nicht', 'ohne', 'no', 'not'} for word in prefix):
                    continue
                count = int(match[1]) if match[1].isdigit() else WORDS[match[1]]
                if count > 1000:
                    raise ValueError('Maximal 1000 Geräte pro Geräteart.')
                label = match[2]
                if re.search(rule['generic'], label):
                    declared = max(declared, count)
                else:
                    groups[label] = max(groups.get(label, 0), count)
        result[role] = max(declared, sum(groups.values()))
        if rule.get('additional_compute'):
            source = text.lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
            source = re.sub(r'[^a-z0-9\n]+', ' ', source)
            additional = {}
            for match in re.finditer(r'\b' + NUMBER + r'\s+(' + rule['additional_compute'] + r')\b', source):
                if re.search(r'\b(?:kein\w*|nicht|ohne)\s*$', source[:match.start()]): continue
                number = int(match[1]) if match[1].isdigit() else WORDS[match[1]]
                if number > 1000:
                    raise ValueError('Maximal 1000 Geräte pro Geräteart.')
                additional[match[2]] = max(additional.get(match[2], 0), number)
            result[role] += sum(additional.values())
    return result
