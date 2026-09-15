"""Recognize project design requests without pretending that a search creates a model."""
import re


def is_project_request(prompt: str) -> bool:
    text = prompt.strip()
    if len(text) > 16000 or 'Strukturierte Vorgaben fuer den Engineering-Agenten:' in text:
        return False
    if re.search(r'\b(?:kein(?:e[nsrm]?)?|nicht|no|not)\s+(?:neues?\s+)?(?:projekt|project|anlage|system)\b', text, re.I):
        return False
    if re.match(r'(?:wie|warum|zeige|suche|finde|erkläre|how|why|show|find|search)\b', text, re.I):
        return False
    desire = re.search(r'\b(?:ich\s+(?:möchte|moechte|will|brauche|benötige)|i\s+(?:want|need)|'
                       r'erstelle|erzeuge|plane|entwickle|create|build|design)\b', text, re.I)
    project = re.search(r'\b(?:projekt|project|anlage|system)\b', text, re.I)
    equipment = re.search(r'sensor|aktor|actuator|ventil|valve|raspberry|respary|controller', text, re.I)
    brief = re.match(r'(?:(?:ein|das)\s+)?neues?\s+projekt\s+(?:mit|für|fuer)\b|(?:a\s+)?new\s+project\s+(?:with|for)\b', text, re.I)
    return bool((desire or brief) and project and equipment)


def project_intake_text(requirement: str) -> str:
    """Keep source requirements intact; suggestions are never confirmed specifications."""
    temperature = bool(re.search(r'temperatur|temperature', requirement, re.I))
    valves = bool(re.search(r'ventil|valve', requirement, re.I))
    pi = bool(re.search(r'(?:raspberry|rasperry|respary)[\s-]*pi|\braspi\b', requirement, re.I))
    lines = ['Daraus lässt sich ein Projektentwurf entwickeln. Deine Vorgabe:', requirement]
    if pi and temperature and valves:
        lines += [
            'Entwurf: Temperatursensoren → Raspberry Pi → Ventilansteuerung → Ventile. '
            'Der Raspberry Pi übernimmt die Verarbeitung der Messwerte und die Steuerfunktion. '
            '„respary pi“ verstehe ich dabei als Raspberry Pi.',
            'Lokale Messwerte und Stellbefehle bleiben im lokalen System; eine Weiterleitung '
            'an andere Systeme wird nur bei ausdrücklich gewünschter Nutzung eingeplant.',
            'Die Regelungsaufgabe muss festlegen, welcher Messwert welches Ventil beeinflusst '
            'und ob automatisch nach Solltemperatur geregelt oder manuell geschaltet wird.',
            'Anschlüsse, geeignete Ausgangstreiber, Versorgung und Abtast-/Schaltzeiten '
            'bleiben bis zur Klärung offen. Eine direkte elektrische Ansteuerung der '
            'Ventile durch den Pi ist damit nicht bestätigt.',
        ]
    else:
        lines += ['Diese Angaben werden als editierbarer Projektentwurf gespeichert. '
                  'Geräte und Funktionen, ihre Zuordnung, Verbindungen und Zeitverhalten werden geprüft. '
                  'Bitte ergänze insbesondere noch ungenannte Stückzahlen, vorhandene Gerätetypen '
                  'und das gewünschte Verhalten der Steuerung. Unbekannte Anschlüsse sind keine bestätigten Verbindungen.']
    lines += ['Du kannst den gespeicherten Entwurf hier ergänzen und einen Modellvorschlag erstellen. '
              'Die Übernahme ins Modell erfordert die Prüfung und Freigabe des konkreten Vorschlags. '
              'Bisher wurde kein Modell angelegt oder verändert.']
    return '\n\n'.join(lines)
