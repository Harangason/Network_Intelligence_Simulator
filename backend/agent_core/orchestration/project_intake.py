"""Recognize project design requests without pretending that a search creates a model."""
import re


def is_project_request(prompt: str) -> bool:
    text = prompt.strip()
    if len(text) > 16000 or 'Strukturierte Vorgaben fuer den Engineering-Agenten:' in text:
        return False
    if re.search(r'\b(?:kein(?:e[nsrm]?)?|nicht|no|not)\s+(?:neues?\s+)?(?:projekt|project|anlage|system)\b', text, re.I):
        return False
    if re.match(r'(?:bitte\s+)?(?:wie|warum|zeige|suche|finde|erkläre|prüfe|prüfen|pruefe|validiere|berechne|how|why|show|find|search|check|validate|calculate)\b', text, re.I):
        return False
    # A hardware brief is a whole-design request even without the word
    # "project". Requiring that word routed inventories into signal/function
    # generators and silently reduced their scope. At least two quantified
    # device roles distinguish a brief from a single-object operation.
    number = r'(?:\d+|ein(?:e[nsrm]?)?|zwei|drei|vier|fünf|fuenf|sechs|sieben|acht|neun|zehn)'
    qualifier = r'(?:(?:lokale|zentrale[nrms]?|kleinen|digitale|intelligente|elektrische|funktionalen|sicherheitsrelevante|embedded|edge|motion|safety|zone|smart|io-link)\s+){0,3}'
    roles = [
        r'(?:[\w/-]*sensor(?:en|s)?|messstellen|messknoten|encoder|positionsrückführungen)',
        r'(?:[\w/-]*aktor(?:en)?|actuators?|(?:servo|motor)\s+drives?|[\w-]*antriebe|lüfter|schaltelemente)',
        r'(?:[\w/-]*controller|steuerung(?:en)?|[\w/-]*steuerungen?|plcs?|[\w-]*rechner|recheneinheiten|raspberry\s*pi|steuerungs-/rechenknoten)',
    ]
    quantified_roles = sum(bool(re.search(r'\b' + number + r'\s+' + qualifier + role + r'\b', text, re.I)) for role in roles)
    existing_edit = re.search(r'\b(?:lösche|entferne|delete|remove|benenne|rename|verschiebe|move|ändere|aendere|update|modify)\b', text, re.I)
    if quantified_roles >= 2 and not existing_edit:
        return True
    desire = re.search(r'\b(?:ich\s+(?:möchte|moechte|will|brauche|benötige)|i\s+(?:want|need)|'
                       r'erstelle|erzeuge|plane|entwickle|create|build|design)\b', text, re.I)
    project = re.search(r'\b(?:projekt|project|[\w-]*anlage|[\w-]*system)\b', text, re.I)
    equipment = re.search(r'sensor|aktor|actuator|ventil|valve|raspberry|respary|controller', text, re.I)
    brief = re.match(r'(?:(?:ein|das)\s+)?neues?\s+projekt\s+(?:mit|für|fuer)\b|(?:a\s+)?new\s+project\s+(?:with|for)\b', text, re.I)
    return bool((desire or brief) and project and equipment)


def project_intake_text(requirement: str, devices: list[dict] | None = None) -> str:
    """Describe the actual draft inventory without inventing a control chain."""
    if devices is None:
        from backend.engineering.agent_tools.project_draft import parse_requirement
        devices = parse_requirement(requirement)['devices']
    labels = {'CONTROLLER': 'Controller', 'GATEWAY': 'Gateways',
              'SENSOR': 'Sensoren', 'ACTUATOR': 'Aktoren'}
    lines = ['Daraus lässt sich ein Projektentwurf entwickeln. Deine Vorgabe:', requirement]
    inventory = []
    for role, label in labels.items():
        members = [device for device in devices if device['role'] == role]
        if members:
            inventory.append(label + ': ' + ', '.join(device['name'] for device in members))
    if inventory:
        lines += ['Geräte im Entwurf:\n' + '\n'.join(inventory)]
    lines += [
        'Geräteaufgaben, Controller-Zuordnungen und das gewünschte Regelungsverhalten '
        'werden anhand deiner Angaben geprüft. Aus einer gemeinsamen Geräteliste '
        'folgt noch keine bestätigte Steuerkette.',
        'Lokale Messwerte und Stellbefehle bleiben im lokalen System; eine Weiterleitung '
        'an andere Systeme wird nur bei ausdrücklich gewünschter Nutzung eingeplant.',
        'Nicht angegebene Anschlüsse, geeignete Ausgangstreiber, Versorgung und '
        'Abtast-/Schaltzeiten bleiben bis zur Klärung offen. Eine direkte elektrische '
        'Ansteuerung ist damit nicht bestätigt.',
        'Du kannst den gespeicherten Entwurf hier ergänzen und einen Modellvorschlag erstellen. '
        'Die Übernahme ins Modell erfordert die Prüfung und Freigabe des konkreten Vorschlags. '
        'Bisher wurde kein Modell angelegt oder verändert.',
    ]
    return '\n\n'.join(lines)
