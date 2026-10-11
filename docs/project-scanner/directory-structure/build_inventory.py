"""DE: Erstellt eine belegte Dateiübersicht ohne Projektcode auszuführen.

EN: Builds a source-backed file inventory without executing project code.
"""

from __future__ import annotations

import ast
import csv
from collections import Counter
from datetime import datetime
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import tokenize
import tomllib
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
EXCLUDED_NAMES = {
    '.git': 'Git-Objektdaten und Versionsverwaltung',
    'node_modules': 'Installierte JavaScript-Abhängigkeiten/Fremdcode',
    '.venv': 'Installierte Python-Umgebung/Fremdcode',
    'venv': 'Installierte Python-Umgebung/Fremdcode',
    '__pycache__': 'Generierter Python-Bytecode',
    '.pytest_cache': 'Generierter Pytest-Cache',
    '.mypy_cache': 'Generierter Typprüfungs-Cache',
    '.ruff_cache': 'Generierter Stilprüfungs-Cache',
    '.idea': 'Lokale IDE-Konfiguration',
    '.vscode': 'Lokale Editor-Konfiguration',
    '.pnpm-store': 'Installierter Paketcache',
    '.uv-cache': 'Installierter Python-Paketcache',
    '.tool-checker': 'Generierte Testmanager-Daten',
    '.ppt_inspect': 'Temporäre Präsentationsinspektion',
    '.ollamassist': 'Lokale Assistenzkonfiguration',
    '.codex-finalizer': 'Lokale Agent-Zustandsdaten',
    'runtime': 'Laufzeitdaten, Jobs, Logs, Prüfläufe und Modelle',
    'test-output': 'Generierte Testausgaben',
    'test-results': 'Generierte Browser-Testausgaben',
    'playwright-report': 'Generierte Browser-Testberichte',
    'SAVED': 'Generierte Simulations- und Trace-Exporte',
    'traces': 'Generierte Trace-Archive',
    'work': 'Lokale Arbeits- und Research-Artefakte',
    'reports': 'Generierte historische Prüfberichte',
    'artifacts': 'Generierte Release-/Prüfartefakte',
    'presentation_output': 'Generierte Präsentationen',
    'implementation-workloads': 'Historische Before/After-/Diff-Arbeitsarchive',
    'project-scanner': 'Bestehende und aktuelle Scanner-Ausgaben (Selbstreferenz)',
    'dist': 'Generierte Build-Ausgaben',
    'build': 'Generierte Build-Ausgaben',
    '.tmp': 'Temporäre lokale Dateien',
    'coverage': 'Generierte Testabdeckung',
    'htmlcov': 'Generierte Testabdeckung',
}
TEXT_EXT = {
    '.py', '.pyi', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
    '.md', '.txt', '.json', '.toml', '.yaml', '.yml', '.css', '.scss',
    '.sql', '.ps1', '.bat', '.sh', '.svg', '.xml', '.html', '.ini',
    '.cfg', '.example', '.diff', '.csv', '.lock',
}
MANUAL = {
    '.dockerignore': 'Regeln für den Docker-Buildkontext: schließt lokale Geheimnisse, Abhängigkeiten, Runtime, Testausgaben, Prüfevidence und Arbeitsarchive vom Image aus.',
    '.gitattributes': 'Git-Regeln für Textnormalisierung und Zeilenenden sowie Binärbehandlung von Datenbanken, Bildern, Dokumenten und Traceformaten.',
    '.gitignore': 'Git-Ausschlussregeln für Geheimnisse, Python-/Next.js-Caches, Runtime, Trace-Exporte, Modellartefakte und lokale Datenbanken; einzelne Ausnahmen bleiben sichtbar.',
    '.codex_ppt_inspect.mjs': 'Lokaler Präsentationshelfer: importiert eine PowerPoint-Datei mit artifact-tool und schreibt einen Inspektionssnapshot sowie eine Folienmontage.',
    'host_metrics_bridge.py': 'Liefert Windows-Hostmetriken für die Docker-NIS-Oberfläche über einen separaten HTTP-Dienst; sammelt Systemzeiten und Speicherinformationen.',
    'start-networkis.bat': 'Windows-Einstieg: ruft den PowerShell-Launcher im Projektverzeichnis auf und gibt dessen Exitcode weiter.',
    'start-networkis.ps1': 'Docker-Launcher mit optionalem Release-Receipt: liest Ressourcenpfade, prüft Docker/Compose und Ports und startet den konfigurierten Stack.',
    'start-networkis-local-ai.bat': 'Lokaler Windows-Launcher: lädt Provider-/Modell-/Worker-Ressourcen und startet den gemeinsamen Python-Launcher mit der lokalen KI-Konfiguration.',
    'README.md': 'Projektbeschreibung, neun Engineering-Schritte, Installation, Launcher, KI-Ressourcen, Persistenz und Betriebsgrenzen.',
    'AGENTS.md': 'Verbindliche Projektwurzel, fachliche Vertragsreferenzen, isolierte Prüfungen und autorisierter Release-/Deployment-Ablauf.',
    'LICENSE': 'Proprietäre NIS-Lizenz und Bedingungen für Nutzung und Weitergabe.',
    'generate_realistic_communication_tool.py': 'Gemeinsamer CLI-/Web-Launcher: liest Ressourcen, prüft Datenbank und lokale KI, startet und überwacht Backend/Frontend mit festen Ports.',
    'Dockerfile': 'Container-Build mit Python-/Node-Laufzeit, gesperrten Python-Abhängigkeiten, npm ci, Build-Identität und Next.js-Produktionsbuild.',
    'docker-compose.networkis.yml': 'Produktionsstack aus PostgreSQL und NIS, Healthchecks, Ports, KI-/Ressourcenvariablen und persistenten Runtime-/Trace-Volumes; Werte werden nicht kopiert.',
    'frontend/package.json': 'Frontend-Abhängigkeiten und npm-Befehle für Entwicklung, Build, Typprüfung, Modultests und Playwright-E2E.',
    'backend/pyproject.toml': 'Python-Projektdefinition, unterstützte Python-Versionen sowie Runtime- und Entwicklungsabhängigkeiten.',
    'backend/app/__init__.py': 'Flask-App-Factory: registriert Simulator-, Trace-, Engineering- und Agent-APIs; stellt unterbrochene Läufe wieder her und konfiguriert CORS.',
    'backend/app/__main__.py': 'Startet das Flask-Backend mit Waitress oder Entwicklungsserver und exklusiver Portbindung; liest Laufzeit- und Worker-Konfiguration.',
    'backend/app/api.py': 'HTTP-Endpunkte für Health/Readiness, Build-Identität, Storage, Jobs, Simulation und Trace-Zugriff; löst projektgebundene Requests auf.',
    'backend/engineering/repository.py': 'Generische PostgreSQL-Persistenz für kanonische Engineering-Entitäten mit CRUD, Versionierung, Governance und Entitätsvalidierung.',
    'backend/engineering/db.py': 'PostgreSQL-Verbindungspool, Projektlocks und lazy Request-Transaktionen; erkennt veraltete Revisionen und invalidiert abhängige Workflow-Ergebnisse.',
    'backend/engineering/workflow/service.py': 'Persistiert Workflowzustand, Quellversionen, Invalidierung und Snapshots; normalisiert Wizardumfang und verarbeitet projektbezogene Zustandsübergänge.',
    'backend/communication/technologies/core/models.py': 'Branchenneutrale Typen für Hardware, Interfaces, Technologieprofile/-stacks, Transportanforderungen und Payload; trennt physische, Protokoll- und Anwendungsebenen.',
    'backend/communication/technologies/core/registry.py': 'Erweiterbare Registry für Profile, Aliasse, Bindings, Generatoren, Validatoren, Codecs und Last-/Timingmodelle; normalisiert Technologieidentitäten.',
    'backend/simulator/model_based_simulation.py': 'Deterministische modellbasierte Signal-, Verhaltens-, Codec- und Fehlersimulation; definiert Verhaltenstypen, Faultklassen und Trace-Limits.',
    'backend/agent_core/core/engineering_agent.py': 'Orchestriert Engineering-Aufträge über den MCP-Client, begrenztes Reasoning, strukturierte Antworten, Vorschläge und Fortschritt.',
    'backend/simulator_engineering_mcp/server.py': 'Registriert typisierte projektgebundene MCP-Tools/Ressourcen; validiert Eingaben und delegiert Berechtigungen und Fachoperationen an den Python-Core.',
    'backend/communication/technologies/__init__.py': 'Erzeugt die zentrale Technologie-Registry, registriert Standarddefinitionen und lädt freigegebene Technologiepacks über den Onboarding-Service.',
    'frontend/src/app/page.tsx': 'Marketing-Startseite mit Model-/Simulate-/Inspect-Beschreibung und projektbewussten Links zur Projekt- und Trace-Auswahl.',
    'frontend/src/app/workflow/page.tsx': 'Marketing-Seite zum Ablauf Configure, Validate, Simulate und Inspect/Export; verlinkt den Studio-Einstieg.',
    'frontend/src/app/studio/page.tsx': 'Studio-Einstieg: erhält die Projekt-ID aus Suchparametern, leitet ohne Modus zur Engineering-Seite weiter und zeigt sonst Netzwerk-/Parameteransichten.',
    'frontend/src/app/api/_backend.ts': 'Next.js-Backendproxy: erhält Projekt-ID aus Header, Query oder Payload, reicht JSON-Anfragen weiter und setzt Timeout sowie Cache-/Antwortheader.',
    'frontend/src/lib/workflow-api.ts': 'Typen und HTTP-Client für projektbezogenen Workflow, Revisionen, Parameter, Topologie, Capacity, Preflight und Simulationssnapshots.',
    'backend/docs/WORKFLOW_ARCHITECTURE.md': 'Dokumentierter Neun-Schritt-Workflow, Status/Invalidierung, Mehrbrowserkonflikte, Snapshots, Capacity-API und Human-Review-Governance.',
}
AREA = {
    'backend/app': 'Flask-Webanwendung, Jobs und Trace-Zugriff',
    'backend/engineering': 'Kanonisches Engineering-Modell und Fachoperationen',
    'backend/communication': 'Technologieprofile, Mechanismen und Registry',
    'backend/simulator': 'Simulationskern, Scheduling, Physik und Trace-Erzeugung',
    'backend/agent_core': 'Projektgebundene Agent-Orchestrierung',
    'backend/simulator_engineering_mcp': 'MCP-Transport und Tool-Registrierung',
    'backend/intelligence': 'Analyse, Diagnose und Vorschläge',
    'backend/knowledge': 'Wissensverwaltung',
    'backend/nis': 'NIS-Fachmodule',
    'backend/workflow': 'Workflow-Modulstruktur',
    'backend/specializations': 'Fachliche Spezialisierungen',
    'backend/tests': 'Backend-Regressionsprüfungen',
    'backend/docs': 'Backend-Dokumentation',
    'frontend/src/app': 'Next.js-Seiten und HTTP-Routen',
    'frontend/src/components': 'React-Oberflächenkomponenten',
    'frontend/src/lib': 'Frontend-Typen, Client- und Fachlogik',
    'frontend/src/features': 'Workflow-Funktionsbereiche',
    'frontend/e2e': 'Playwright-E2E-Prüfungen und Fixtures',
    'frontend/public': 'Statische Frontend-Ressourcen',
    'scripts': 'Betriebs-, Reparatur-, Prüf- und Releasewerkzeuge',
    'docs': 'Projektverträge, Architektur und Nachweise',
    'config': 'Persistierte Ressourcen- und Maschinenkonfiguration',
    'tests': 'Übergreifende Projektprüfungen',
    'tool-checker': 'Projektintegrierte Testmanager-Konfiguration',
}


def clean(value, limit=None):
    """DE: Normalisiert Beschreibungen und entfernt erkennbare Zugangsdaten.

    EN: Normalizes descriptions and removes recognizable credentials.
    """
    value = str(value or '')
    value = re.sub(r'([a-z][a-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@', r'\1[REDACTED]@', value, flags=re.I)
    value = re.sub(r'\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}', '[REDACTED]', value)
    value = re.sub(r'(?i)((?:password|passwd|api[_ -]?key|secret|token)\s*[:=]\s*)[^\s,;]+', r'\1[REDACTED]', value)
    value = re.sub(r'\s+', ' ', value).strip()
    return value if limit is None or len(value) <= limit else value[:limit].rsplit(' ', 1)[0] + ' …'


def excluded_reason(path):
    """DE: Entscheidet transparente Verzeichnisausnahmen ohne Links zu folgen.

    EN: Selects transparent directory exclusions without following links.
    """
    name = path.name
    if name in EXCLUDED_NAMES:
        return EXCLUDED_NAMES[name]
    if name.startswith(('.next', '.tmp', '.test-results', '.codex-pytest')):
        return 'Generiertes Build-/Test-/Temporärverzeichnis'
    if name.startswith('generated_'):
        return 'Generierte Simulationspakete'
    if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
        return 'Symlink/Junction/Reparsepunkt: nicht verfolgt'
    return None


def enumerate_files():
    """DE: Inventarisiert vorhandene Dateien einschließlich ignorierter Quellen.

    EN: Inventories existing files including ignored source files.
    """
    files, exclusions, directories, errors = [], [], [], []

    def on_error(error):
        errors.append({'path': str(error.filename), 'reason': clean(error)})

    for folder, dirs, names in os.walk(ROOT, followlinks=False, onerror=on_error):
        parent = Path(folder)
        directories.append(parent.relative_to(ROOT).as_posix())
        for name in sorted(dirs):
            child = parent / name
            try:
                reason = excluded_reason(child)
            except OSError as error:
                reason = 'Verzeichnis nicht lesbar: ' + clean(error)
            if reason:
                dirs.remove(name)
                exclusions.append({'path': child.relative_to(ROOT).as_posix(), 'kind': 'directory', 'reason': reason})
        for name in sorted(names):
            path = parent / name
            rel = path.relative_to(ROOT).as_posix()
            suffix = path.suffix.lower()
            reason = None
            if name.startswith('.env') and not name.endswith('.example') or suffix in {'.pem', '.key', '.p12', '.pfx'}:
                reason = 'Geheimnis-/Zertifikatsdatei: Inhalt nicht gelesen'
            elif path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                reason = 'Symlink/Reparsepunkt: nicht gelesen'
            elif suffix in {'.pyc', '.pyo', '.log', '.pid', '.tsbuildinfo'}:
                reason = 'Generierter Cache/Log/Prozessstatus'
            if reason:
                exclusions.append({'path': rel, 'kind': 'file', 'reason': reason})
            else:
                files.append(path)
    return sorted(files), sorted(exclusions, key=lambda v: v['path']), sorted(directories), errors


def python_details(source, rel):
    """DE: Extrahiert Modultexte, Definitionen und Routen ausschließlich per AST.

    EN: Extracts module text, definitions and routes using AST only.
    """
    tree = ast.parse(source, filename=rel)
    symbols, imports, routes, constants = [], [], [], []

    def visit(node, scope=''):
        for child in ast.iter_child_nodes(node):
            child_scope = scope
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = scope + child.name
                symbols.append({'name': qualified, 'kind': 'Klasse' if isinstance(child, ast.ClassDef) else 'Funktion/Methode', 'line': child.lineno, 'description': clean(ast.get_docstring(child), 420)})
                child_scope = qualified + '.'
                for decorator in child.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr in {'route', 'get', 'post', 'put', 'patch', 'delete'} and decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                        methods = [decorator.func.attr.upper()]
                        for keyword in decorator.keywords:
                            if keyword.arg == 'methods':
                                try:
                                    methods = ast.literal_eval(keyword.value)
                                except (ValueError, TypeError):
                                    methods = ['DYNAMISCH']
                        routes.append({'path': clean(decorator.args[0].value), 'methods': methods, 'line': child.lineno, 'function': qualified})
            visit(child, child_scope)
    visit(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append('.' * node.level + (node.module or ''))
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        constants.extend(t.id for t in targets if isinstance(t, ast.Name) and t.id.isupper())
    return {'module_description': clean(ast.get_docstring(tree), 700), 'symbols': symbols, 'imports': sorted(set(imports)), 'routes': routes, 'constants': constants, 'evidence': 'Python-AST und Modul-/Symboltexte gelesen; Verhalten nicht ausgeführt'}


def classify(rel, suffix):
    """DE: Ordnet Dateien für die Navigation nach Inhaltstyp ein.

    EN: Classifies files by content type for navigation.
    """
    if '/tests/' in rel or rel.startswith('tests/') or '.test.' in rel or '.spec.' in rel or rel.startswith('frontend/e2e/') and suffix in {'.ts', '.js', '.mjs'}:
        return 'Tests'
    if suffix == '.md' or rel == 'LICENSE' or suffix == '.txt' and 'requirements' not in rel:
        return 'Dokumentation'
    if 'lock' in Path(rel).name:
        return 'Lockfile'
    if suffix in {'.json', '.toml', '.yml', '.yaml', '.ini', '.cfg', '.example'} or Path(rel).name in {'Dockerfile', '.gitignore', '.dockerignore', '.gitattributes'}:
        return 'Konfiguration'
    if suffix in {'.py', '.pyi', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.ps1', '.bat', '.sh', '.sql'}:
        return 'Quellcode'
    if suffix in {'.css', '.scss', '.svg', '.png', '.jpg', '.jpeg', '.ico', '.woff', '.woff2', '.html'}:
        return 'UI-Ressource'
    return 'Daten/Artefakt'


def inspect_file(path):
    """DE: Beschreibt eine Datei mit überprüfbaren strukturellen Inhaltsbelegen.

    EN: Describes a file using verifiable structural content evidence.
    """
    rel, suffix = path.relative_to(ROOT).as_posix(), path.suffix.lower()
    record = {'path': rel, 'category': classify(rel, suffix), 'symbols': [], 'imports': [], 'routes': []}
    try:
        record['bytes'] = path.stat().st_size
        if record['bytes'] > 2_000_000:
            record.update(description='Große Datei; nur Pfad und Größe erfasst. Inhalt nicht gelesen.', evidence='Größenlimit 2 MB; Inhaltsprüfung offen')
            return record
        raw = path.read_bytes()
        record['sha256'] = hashlib.sha256(raw).hexdigest()
        text_like = suffix in TEXT_EXT or path.name in {'Dockerfile', 'LICENSE', '.gitignore', '.dockerignore', '.gitattributes'}
        if path.name == '.gitkeep':
            record.update(description='Platzhalter, damit das zugehörige Verzeichnis in Git erhalten bleibt; keine Anwendungslogik.', evidence='Dateiname und kleiner Platzhalterinhalt gelesen')
            return record
        if not text_like or b'\x00' in raw[:4096]:
            record.update(description='Binär-/Sonderdatei; Dateigröße und SHA-256 erfasst. Binärinhalt nicht interpretiert.', evidence='Metadaten und Hash; Inhalt offen')
            return record
        if suffix in {'.py', '.pyi'}:
            with tokenize.open(path) as stream:
                source = stream.read()
        else:
            source = raw.decode('utf-8-sig', errors='replace')
        record['lines'] = len(source.splitlines())
        record['evidence'] = 'Text strukturell gelesen; keine Ausführung'
        if suffix in {'.py', '.pyi'}:
            try:
                record.update(python_details(source, rel))
            except SyntaxError as error:
                record['parse_error'] = f'{error.msg} (Zeile {error.lineno})'
                record['evidence'] = 'Text gelesen; Python-AST fehlgeschlagen'
        elif suffix in {'.md', '.txt'} or path.name == 'LICENSE':
            record['headings'] = [clean(m.group(1), 160) for m in re.finditer(r'^#{1,6}\s+(.+)$', source, re.M)]
            prose = []
            fenced = False
            for line in source.splitlines():
                if line.startswith('```'):
                    fenced = not fenced
                    continue
                line = line.strip()
                if not fenced and line and not line.startswith(('#', '|', '<!--', '---', '- ', '* ', '>')):
                    prose.append(line)
                    if len(prose) == 3:
                        break
            record['module_description'] = clean(' '.join(prose), 600)
            record['browser_snapshot'] = bool(re.search(r'^\s*- (?:button|link|heading|textbox|generic) ', source, re.M))
        elif suffix == '.json':
            try:
                data = json.loads(source)
                record['keys'] = list(data) if isinstance(data, dict) else []
                record['data_type'] = type(data).__name__
                if isinstance(data, list):
                    record['items'] = len(data)
                    if data and isinstance(data[0], dict):
                        record['item_keys'] = list(data[0])
            except ValueError:
                record['parse_error'] = 'JSON nicht vollständig parsebar'
        elif suffix == '.toml':
            try:
                record['keys'] = list(tomllib.loads(source))
            except ValueError:
                record['parse_error'] = 'TOML nicht parsebar'
        elif suffix == '.csv':
            rows = list(csv.reader(source.splitlines()))
            record['csv_columns'] = rows[0] if rows else []
            record['data_rows'] = max(0, len(rows) - 1)
        elif suffix == '.xml':
            try:
                xml = ET.fromstring(source)
                record['xml_root'] = xml.tag
                record['xml_elements'] = dict(Counter(node.tag for node in xml.iter()))
            except ET.ParseError:
                record['parse_error'] = 'XML nicht parsebar'
        elif suffix in {'.yml', '.yaml', '.example', '.ini', '.cfg'}:
            record['keys'] = list(dict.fromkeys(re.findall(r'^\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*[:=]', source, re.M)))
        elif suffix in {'.css', '.scss'}:
            record['selectors'] = [clean(v, 150) for v in re.findall(r'([^{}]+)\{', source)[:16]]
        elif suffix == '.sql':
            record['sql_objects'] = re.findall(r'\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|INDEX|VIEW|FUNCTION)\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w.]+)', source, re.I)
        elif suffix in {'.bat', '.ps1', '.sh'}:
            record['commands'] = sorted(set(re.findall(r'\b(?:python|uv|npm|node|docker|ollama|Start-Process|Invoke-WebRequest|powershell|pwsh)\b', source, re.I)))
        elif suffix == '.svg':
            record['module_description'] = 'SVG-Vektorgrafik; ' + ('mit viewBox ' + re.search(r'viewBox=["\x27]([^"\x27]+)', source).group(1) if 'viewBox=' in source else 'XML-Grafikdefinition')
        return record
    except OSError as error:
        record.update(description='Datei nicht lesbar: ' + clean(error), evidence='Lesefehler; Inhalt offen', error=clean(error))
        return record


def summarize(record):
    """DE: Formuliert Beschreibungen aus tatsächlich extrahierten Inhaltsbelegen.

    EN: Forms descriptions from extracted content evidence.
    """
    rel = record['path']
    if rel in MANUAL:
        record['description'] = MANUAL[rel]
        record['evidence'] = 'Gezielt quellengeprüfte Inhaltsbeschreibung; zusätzliche Struktur statisch extrahiert'
        return
    if record.get('description'):
        return
    parts = []
    if record.get('module_description'):
        parts.append(record['module_description'])
    tests = record.get('test_titles') or [s['name'] for s in record['symbols'] if s['name'].split('.')[-1].startswith('test_')]
    if tests:
        parts.append('Prüffälle: ' + ', '.join(tests[:6]) + (' …' if len(tests) > 6 else '') + '.')
    primary = [s for s in record['symbols'] if '.' not in s['name'] and not s['name'].startswith('_')]
    if primary:
        parts.append('Definitionen: ' + ', '.join(s['name'] for s in primary[:8]) + (' …' if len(primary) > 8 else '') + '.')
    if record.get('headings'):
        parts.append('Abschnitte: ' + '; '.join(record['headings'][:5]) + '.')
    if record.get('keys'):
        parts.append('Konfigurations-/Datenbereiche: ' + ', '.join(record['keys'][:14]) + (' …' if len(record['keys']) > 14 else '') + '; Werte nicht kopiert.')
    if record.get('data_type') == 'list':
        parts.append(f"JSON-Liste mit {record['items']} Einträgen" + ('; Felder: ' + ', '.join(record.get('item_keys', [])[:12]) if record.get('item_keys') else '') + '.')
    if record.get('sql_objects'):
        parts.append('SQL-Objekte: ' + ', '.join(record['sql_objects'][:14]) + '.')
    if record.get('csv_columns'):
        parts.append(f"CSV-Tabelle mit {record['data_rows']} Datenzeilen; Spalten: " + ', '.join(record['csv_columns']) + '.')
    if record.get('xml_root'):
        parts.append('XML-Dokument mit Wurzelelement ' + record['xml_root'] + '; Elemente: ' + ', '.join(f'{key} ({value})' for key, value in record['xml_elements'].items()) + '.')
    if record.get('selectors'):
        parts.append('CSS-Regeln, unter anderem für ' + '; '.join(record['selectors'][:5]) + '.')
    if record.get('commands'):
        parts.append('Shell-Anweisungen verwenden: ' + ', '.join(record['commands']) + '.')
    if record['category'] == 'Lockfile':
        parts = ['Abhängigkeitssperre mit Paketauflösung/Versionsständen; automatisch verwalteter Inhalt, nicht fachlich interpretiert.']
    if not parts and record['imports']:
        parts.append('Import-/Exportmodul; eingebundene Module: ' + ', '.join(record['imports'][:8]) + '.')
    if not parts and record['symbols']:
        parts.append('Definitionen: ' + ', '.join(s['name'] for s in record['symbols'][:10]) + '.')
    if not parts and record.get('constants'):
        parts.append('Modulkonstanten: ' + ', '.join(record['constants'][:12]) + '; Werte nicht kopiert.')
    if not parts:
        if record.get('browser_snapshot'):
            parts.append('Gespeicherter Browser-Zustandsauszug mit Rollen, Bedienelementen und sichtbaren Oberflächentexten; historische Prüf-Evidence.')
        else:
            parts.append('Leere Datei.' if not record.get('bytes') else 'Textdatei ohne extrahierbare Beschreibung/Definitionen; fachlicher Inhalt offen.')
    record['description'] = clean(' '.join(parts), 1100)


def tree_lines(records, excluded, directories):
    """DE: Gibt alle erfassten Pfade und expliziten Auslassungen als Baum aus.

    EN: Renders all inventoried paths and explicit exclusions as a tree.
    """
    tree = {}
    def insert(path, label, directory=False):
        node = tree
        pieces = path.split('/')
        for part in pieces[:-1]:
            node = node.setdefault(part + '/', {})
        node[pieces[-1] + ('/' if directory else '')] = {} if label == 'directory' else label
    for directory in directories:
        if directory != '.':
            insert(directory, 'directory', directory=True)
    for record in records:
        insert(record['path'], record)
    for entry in excluded:
        insert(entry['path'], entry, directory=entry['kind'] == 'directory')
    lines = [ROOT.name + '/']
    def emit(node, prefix):
        items = sorted(node.items(), key=lambda x: (not isinstance(x[1], dict) or 'path' in x[1], x[0].casefold()))
        for index, (name, value) in enumerate(items):
            last = index == len(items) - 1
            annotation = ' [ausgenommen: ' + value['reason'] + ']' if isinstance(value, dict) and 'reason' in value else ''
            lines.append(prefix + ('└── ' if last else '├── ') + name + annotation)
            if isinstance(value, dict) and 'path' not in value:
                emit(value, prefix + ('    ' if last else '│   '))
    emit(tree, '')
    return lines


def write_outputs(records, excluded, directories, errors, revision):
    """DE: Schreibt Baum, Markdown, JSON und offline durchsuchbares HTML.

    EN: Writes a tree, Markdown, JSON and offline searchable HTML.
    """
    stamp = datetime.now(ZoneInfo('Europe/Berlin')).isoformat(timespec='seconds')
    counts = Counter(r['category'] for r in records)
    inventory = {'root': str(ROOT), 'created_at': stamp, 'revision': revision, 'scope': 'Vorhandene Projektdateien; ausgeschlossene Verzeichnisse werden nicht rekursiv inventarisiert. Keine Garantie für parallele Änderungen nach dem Scan.', 'files': records, 'excluded': excluded, 'directories': directories, 'errors': errors, 'counts': dict(counts)}
    (OUT / 'inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tree = tree_lines(records, excluded, directories)
    (OUT / 'directory-tree.txt').write_text('\n'.join(tree) + '\n', encoding='utf-8')
    md = ['# Simulator: Verzeichnisstruktur und Dateiinhalte', '', f'Projekt: `{ROOT}`  ', f'Stand: {stamp}  ', f'Git-Commit: `{revision}`; analysiert wird der vorhandene Arbeitsbaum, einschließlich lokaler Änderungen.  ', f'Erfasst: {len(records)} Dateien in {len(directories)} besuchten Verzeichnissen.', '', '## Lesen und Umfang', '', '- [Durchsuchbare HTML-Übersicht](index.html): Filter nach Pfad, Inhalt und Dateityp.', '- [Vollständiger Verzeichnisbaum](directory-tree.txt): alle erfassten Pfade sowie die explizit ausgenommenen Stellen.', '- [Maschinenlesbares Inventar](inventory.json): Symbole mit Zeilen, Imports, Routen, Größen, SHA-256 und Prüfstatus.', '- [Scanner-Befunde](scan/audit.md): separate Python-AST-/Dokumentations- und Stilprüfung.', '', 'Inhalte sind Beschreibungen und strukturelle Belege, keine vollständigen Dateikopien. Vorhandene englische Modultexte und Testnamen bleiben als Originalbelege erhalten. Gezielt gelesene zentrale Dateien sind als quellengeprüft markiert; AST-/Parser-Inventar ist keine semantische Vollprüfung. Projektcode wird weder importiert noch ausgeführt. Geheimnisse werden nicht gelesen oder kopiert; Konfigurationswerte werden nicht übernommen. Binärdateien und Dateien über 2 MB erhalten ausdrücklich einen offenen Inhaltsstatus. Abhängigkeiten, Cache-/Runtime-/Exportverzeichnisse und historische Arbeitsarchive werden am tatsächlichen Pfad markiert, ihre einzelnen Dateien werden nicht aufgeführt. Symlinks/Junctions werden nicht verfolgt.', '', 'Nur Dokumentationsartefakte wurden erstellt; Anwendung, Produktdatenbank und laufender Stack sind nicht Gegenstand dieses Auftrags.', '', '## Hauptbereiche', '', '| Bereich | Verantwortung |', '| --- | --- |']
    md.extend(f'| `{area}/` | {purpose} |' for area, purpose in AREA.items())
    md += ['', '## Dateitypen', '', '| Typ | Anzahl |', '| --- | ---: |']
    md.extend(f'| {kind} | {number} |' for kind, number in sorted(counts.items()))
    md += ['', '## Dateiweise Inhaltsbeschreibung', '']
    parent = None
    for record in records:
        current = str(Path(record['path']).parent).replace('\\', '/')
        if current != parent:
            md += ['', '### ' + ('Projektwurzel' if current == '.' else current + '/'), '']
            parent = current
        path_link = '../../../' + record['path']
        md += [f"#### [{Path(record['path']).name}](<{path_link}>)", '', record['description'], '', f"Typ: {record['category']}; {record.get('bytes', '?')} Bytes" + (f"; {record['lines']} Zeilen" if 'lines' in record else '') + '.  ', 'Nachweis: ' + record['evidence'] + '.', '']
        if record['routes']:
            md.append('Routen (lokale Dekoratorpfade; Blueprint-Präfix gesondert auflösen): ' + '; '.join('/'.join(r['methods']) + ' `' + r['path'] + '`' for r in record['routes']) + '.')
        if record['symbols']:
            md.append('Symbole: ' + '; '.join(f"`{s['name']}` (Z. {s['line']})" for s in record['symbols']) + '.')
        if record['imports']:
            md.append('Imports: ' + ', '.join('`' + item + '`' for item in record['imports']) + '.')
        if record.get('parse_error'):
            md.append('Parserbefund: ' + record['parse_error'] + '.')
    md += ['', '## Ausgenommene Stellen', '', '| Pfad | Grund |', '| --- | --- |']
    md.extend(f"| `{item['path']}` | {item['reason']} |" for item in excluded)
    if errors:
        md += ['', '## Lesefehler', ''] + [clean(item) for item in errors]
    (OUT / 'file-descriptions.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    esc = html.escape
    rows = []
    for record in records:
        details = ''
        if record['symbols']:
            details += '<details><summary>Definitionen (' + str(len(record['symbols'])) + ')</summary><ul>'
            details += ''.join('<li><code>' + esc(s['name']) + '</code> · Zeile ' + str(s['line']) + (' — ' + esc(s.get('description', '')) if s.get('description') else '') + '</li>' for s in record['symbols']) + '</ul></details>'
        if record['routes']:
            details += '<p>Routen: ' + esc('; '.join('/'.join(r['methods']) + ' ' + r['path'] for r in record['routes'])) + '</p>'
        if record['imports']:
            details += '<details><summary>Imports</summary><p>' + esc(', '.join(record['imports'])) + '</p></details>'
        search = esc((record['path'] + ' ' + record['description'] + ' ' + ' '.join(s['name'] for s in record['symbols'])).casefold(), quote=True)
        rows.append('<tr data-kind="' + esc(record['category']) + '" data-search="' + search + '"><td><a href="../../../' + esc(record['path'], quote=True) + '"><code>' + esc(record['path']) + '</code></a><small>' + esc(record['category']) + ' · ' + str(record.get('bytes', '?')) + ' Bytes' + (' · ' + str(record['lines']) + ' Zeilen' if 'lines' in record else '') + '</small></td><td><p>' + esc(record['description']) + '</p><small>' + esc(record['evidence']) + '</small>' + details + '</td></tr>')
    options = ''.join('<option>' + esc(key) + '</option>' for key in sorted(counts))
    page = '''<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NIS · Verzeichnisstruktur und Dateiinhalte</title><style>
    :root{font-family:system-ui,sans-serif;color:#dbe5f2;background:#0b1220;color-scheme:dark}body{max-width:1500px;margin:auto;padding:30px}h1{font-size:2rem}a{color:#8fc7ff}p{line-height:1.5}small{display:block;color:#9fb0c9;margin-top:8px}code{overflow-wrap:anywhere}.controls{position:sticky;top:0;background:#0b1220;padding:16px 0;display:flex;gap:12px;flex-wrap:wrap;align-items:center}input,select{padding:12px;border:1px solid #35435b;border-radius:6px;background:#141f31;color:inherit;font:inherit}input{flex:1;min-width:220px}table{width:100%;border-collapse:collapse}th{text-align:left}td,th{padding:16px;border-bottom:1px solid #263449;vertical-align:top}td:first-child{width:37%}td p{margin:0}details{margin-top:12px}summary{cursor:pointer;color:#8fc7ff}li{margin:6px 0}pre{overflow:auto;background:#141f31;padding:16px;font-size:12px;max-height:65vh}tr[hidden]{display:none}@media(max-width:750px){body{padding:15px}td,th{padding:10px}td:first-child{width:40%}}</style>
    <h1>Network Simulator · Verzeichnisstruktur</h1><p>STATS</p><p><code>ROOT</code><br>Arbeitsbaum einschließlich lokaler Änderungen · Commit <code>REV</code></p><p>Inhaltsbeschreibungen je Datei, Definitionen mit Zeilennummern, Imports und lokale HTTP-Routen. Statische Erfassung ist keine semantische Vollprüfung. Geheimnisse, Fremdcode, Cache, Runtime und historische Arbeitsarchive sind explizit ausgenommen; deren Dateien werden nicht rekursiv inventarisiert. Binär- und Großdateien bleiben inhaltlich offen.</p><p><a href="file-descriptions.md">Markdown-Dateikatalog</a> · <a href="directory-tree.txt">Verzeichnisbaum</a> · <a href="inventory.json">JSON-Inventar</a> · <a href="scan/audit.md">Scanner-Prüfbericht</a></p><details><summary>Verzeichnisbaum anzeigen</summary><pre>TREE</pre></details><div class="controls"><label for="search">Suche</label><input id="search" type="search" placeholder="Pfad, Klasse, Funktion oder Inhalt …"><label for="kind">Dateityp</label><select id="kind"><option value="">Alle Dateitypen</option>OPTIONS</select><span id="count" role="status" aria-live="polite"></span></div><table><thead><tr><th>Datei</th><th>Inhalt und Belege</th></tr></thead><tbody>ROWS</tbody></table><script>
    const rows=[...document.querySelectorAll('tbody tr')],search=document.getElementById('search'),kind=document.getElementById('kind'),count=document.getElementById('count');function filter(){const query=search.value.toLocaleLowerCase('de').trim().split(/\\s+/).filter(Boolean);let visible=0;for(const row of rows){const hit=(!kind.value||row.dataset.kind===kind.value)&&query.every(word=>row.dataset.search.includes(word));row.hidden=!hit;if(hit)visible++}count.textContent=visible+' / '+rows.length+' Dateien'}search.addEventListener('input',filter);kind.addEventListener('change',filter);filter();
    </script></html>'''
    substitutions = {'STATS': esc(f'{len(records)} Dateien · {len(directories)} Verzeichnisse · Stand {stamp}'), 'ROOT': esc(str(ROOT)), 'REV': esc(revision), 'TREE': esc('\n'.join(tree)), 'OPTIONS': options, 'ROWS': '\n'.join(rows)}
    for key, value in substitutions.items():
        page = page.replace(key, value)
    (OUT / 'index.html').write_text(page, encoding='utf-8')
    print(json.dumps({'files': len(records), 'directories': len(directories), 'exclusions': len(excluded), 'errors': len(errors), 'categories': dict(counts)}, ensure_ascii=False))


def main():
    """DE: Liest Quellen und optionale TypeScript-Parserdaten und schreibt Berichte.

    EN: Reads sources and optional TypeScript parser data and writes reports.
    """
    paths, excluded, directories, errors = enumerate_files()
    records = [inspect_file(path) for path in paths]
    ts_path = OUT / 'typescript-details.json'
    ts = json.loads(ts_path.read_text(encoding='utf-8')) if ts_path.exists() else {}
    for record in records:
        if record['path'] in ts:
            record.update(ts[record['path']])
        for symbol in record['symbols']:
            symbol['description'] = clean(symbol.get('description'), 420)
        record['module_description'] = clean(record.get('module_description'), 700)
        record['test_titles'] = [clean(title) for title in record.get('test_titles', [])]
        summarize(record)
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    write_outputs(records, excluded, directories, errors, revision)


if __name__ == '__main__':
    main()
