"""Bounded camera clarification; no model writes and no hidden hardware assumptions."""
from uuid import uuid4


def next_camera_decision(answers):
    def question(key, text, options, *, multiple=False, description='', impact='CRITICAL'):
        return {'type':'MULTI_SELECT' if multiple else 'SINGLE_SELECT', 'text':text,
            'metadata':{'decision_key':key}, 'question':{'id':str(uuid4()), 'question':text,
                'description':description, 'selection_mode':'MULTI' if multiple else 'SINGLE',
                'engineering_impact':impact, 'options':options}}
    def option(id, label, description='', recommended=False, reason='', disabled=False):
        return dict(id=id, label=label, description=description, recommended=recommended, reason=reason, disabled=disabled)
    if 'camera_coverage' not in answers:
        return question('camera_coverage', 'Welchen Bereich soll die Kameraüberwachung erfassen?', [
            option('front', 'Frontbereich'), option('front_rear', 'Front und Heck'),
            option('surround', '360°-Umgebung', recommended=True, reason='Deckt die gesamte Fahrzeugumgebung ab; die Sensoranordnung wird anschließend ausdrücklich festgelegt.'),
            option('custom', 'Benutzerdefiniert', 'Bitte die Anforderung im Eingabefeld mit dem gewünschten Bereich präzisieren.', disabled=True)],
            description='Die Abdeckung bestimmt Sensoranzahl, Rechenbedarf und Kommunikationslast.')
    if 'camera_outputs' not in answers:
        return question('camera_outputs', 'Welche Ergebnisse werden benötigt?', [
            option('objects', 'Objektliste', recommended=True, reason='Kompakte erkannte Objekte für nachgelagerte Funktionen.'),
            option('free_space', 'Freiraum', recommended=True, reason='Beschreibt befahrbare Bereiche.'),
            option('status', 'Status und Diagnose', recommended=True, reason='Erlaubt die Bewertung der Verfügbarkeit.'),
            option('raw_image', 'Rohbilder', 'Erfordert eine spätere Dimensionierung aus Auflösung, Bildrate und Kodierung.')], multiple=True)
    if 'camera_profile' not in answers:
        surround = answers['camera_coverage']['selected_options'] == ['surround']
        return question('camera_profile', 'Welche Sensoranordnung soll als Planungsannahme gelten?', [
            option('four_wide' if surround else 'directional', 'Vier Weitwinkelkameras' if surround else 'Eine Kamera je ausgewählter Richtung',
                'Bei 360°: Front, Heck, links, rechts; angenommene 100° horizontale Sicht pro Kamera. Montage und Überlappung müssen geprüft werden.', True,
                'Die Anzahl ergibt sich aus dieser ausdrücklich gewählten Anordnung, nicht allein aus dem Wort Kamera.'),
            option('two_fisheye', 'Zwei Fisheye-Kameras', 'Angenommene 190° Sicht; Verdeckung und Randbereiche müssen geprüft werden.', disabled=not surround),
            option('unspecified', 'Profil noch offen', 'Die Architektur wird erst nach einem belastbaren Sensorprofil erstellt.', disabled=True)],
            description='Dies ist eine überprüfbare Planungsannahme, kein verifiziertes Herstellerprofil.')
    if 'camera_recommendation' not in answers:
        outputs = answers['camera_outputs'].get('labels', answers['camera_outputs']['selected_options'])
        result = question('camera_recommendation', 'Architekturvorschlag auf dieser Grundlage erstellen?', [
            option('propose', 'Vorschlag erstellen', recommended=True, reason='Die Änderungen werden anschließend einzeln geprüft und ausdrücklich freigegeben.'),
            option('revise', 'Angaben überarbeiten', 'Eine neue Anforderung im Eingabefeld beginnt die Klärung erneut.', disabled=True)],
            description='Empfehlung: gewählte Kameras mit Erfassungsfunktionen, Vision Controller, Ethernet-Datenpfade und Daten-/Statusmodelle für '+', '.join(outputs)+'. Rohbild-Bandbreite und Timing bleiben bis zur Dimensionierung offen. Diese Auswahl erteilt keine Modellfreigabe.')
        result.update(type='RECOMMENDATION', title='Empfohlene Architektur', recommendation={'Sensorprofil':answers['camera_profile']['labels'][0], 'Ausgaben':len(outputs), 'Kommunikation':'Ethernet'})
        return result
    return None
