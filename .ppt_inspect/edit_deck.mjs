import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const SKILL_DIR = 'F:/CodexOrdner/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
const workspaceDir = 'I:/PycharmProjects/My_first_Network_Simulator';
const sourcePath = 'H:/OneDrive/Download/Projekte_AI_NIS_ueberarbeitet_Docker_LLM.pptx';
const stagingDir = path.join(workspaceDir, '.codex-finalizer');
const outDir = path.join(workspaceDir, 'presentation_output');
const finalPath = path.join(outDir, 'Projekte_AI_NIS_ueberarbeitet_Docker_LLM_uebersichtlich_v2.pptx');
await fs.mkdir(stagingDir, { recursive: true });
await fs.mkdir(outDir, { recursive: true });

const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const replacements = new Map([
  ['NIS – Engineering\ntrifft KI', 'NIS macht technische\nNetzwerke prüfbar'],
  ['Kommunikationsnetze modellieren · validieren · simulieren · analysieren', 'Ein System, das Kommunikationsnetze beschreibt, berechnet, testet und erklärt'],
  ['Technische Plattformübersicht · Skills · Architektur · Qualitätssicherung', 'Überblick für Engineering, Entwicklung und Management'],
  ['Single Source: Modell → Simulation → Trace → Finding → Repair', 'Ein gemeinsamer Datenstand verbindet Modell, Simulation, Testergebnis, Befund und Reparatur'],
  ['Entwickelte Skills machen NIS ausführbar', 'Was NIS für ein Engineering-Team leistet'],
  ['Die Skills sind nicht nur Oberfläche – sie steuern Prüfung, Ausführung, Kontext und Qualität.', 'Skills sind ausführbare Arbeitsanweisungen: Sie führen durch Aufgaben, wählen Werkzeuge und sichern den Qualitätsprozess.'],
  ['Vom Problem zur geschlossenen Engineering-Schleife', 'Der Ablauf von der Idee bis zum Nachweis'],
  ['Die Präsentation folgt einem durchgängigen Ablauf statt isolierten Einzelthemen.', 'Jede Station baut auf demselben Modell und denselben Prüfergebnissen auf.'],
  ['Kein einzelner KI-Chat, sondern ein kontrollierter Engineering-Prozess mit Modellzustand, Tools, Evidence und Freigabe.', 'NIS ist kein einzelner KI-Chat. Es verbindet Modell, Werkzeuge, Nachweise und Freigaben zu einem kontrollierten Engineering-Prozess.'],
  ['NIS verbindet Modell, Fachlogik und KI in einem Arbeitsraum', 'Was die Plattform abdeckt'],
  ['Die Plattform prüft Kommunikation nicht nur visuell, sondern technisch nachvollziehbar.', 'NIS macht technische Kommunikation berechenbar und die Ergebnisse nachvollziehbar.'],
  ['Vier Schichten halten UI, Agent, Fachlogik und Daten sauber getrennt', 'Technischer Aufbau'],
  ['Die Struktur wird dadurch flüssiger: jede Schicht hat eine klare Aufgabe.', 'Jede Schicht hat eine klare Aufgabe und liefert Ergebnisse an die nächste.'],
  ['UI & Wizards', 'Oberfläche und geführte Schritte'],
  ['Agent & Skills', 'Planung und ausführbare Regeln'],
  ['MCP & Core', 'Werkzeuge und Fachlogik'],
  ['Daten & Evidence', 'Modell und Nachweise'],
  ['Deterministisch, lokale LLMs und Fallback', 'Wie die KI eingesetzt wird'],
  ['NIS nutzt die verlässlichste Ebene zuerst: Fachlogik berechnet, lokale LLMs planen, öffentliche LLMs bleiben optionaler Fallback.', 'Berechnungen bleiben nachvollziehbar. KI hilft bei Planung, Erklärung und Analyse. Öffentliche Modelle bleiben ein kontrollierter Ausnahmeweg.'],
  ['CPU, CUDA und Public Fallback trennen', 'Welche Rechenwege genutzt werden'],
  ['Deterministische Dienste bleiben planbar auf CPU/Worker-Pfaden; lokale Inferenz nutzt GPU/CUDA, wenn verfügbar.', 'Feste Prüfungen laufen planbar. Lokale Modelle nutzen GPU-Leistung, falls vorhanden.'],
  ['Ein Canonical Model verbindet Engineering und Kommunikation', 'Ein gemeinsames Modell verbindet alle technischen Objekte'],
  ['Das Modell ist die gemeinsame Sprache für Architektur, Signale, Simulation und Nachweise.', 'Das gemeinsame Modell verbindet Architektur, Signale, Simulation und Nachweise.'],
  ['Wizards führen – der Engineering Agent erledigt die Arbeit', 'Geführte Schritte und Agent arbeiten zusammen'],
  ['Wizards führen durch Aufgaben. Der Agent plant, wählt Tools und validiert den Abschluss.', 'Wizards führen durch Aufgaben. Der Agent plant, wählt Werkzeuge und prüft den Abschluss.'],
  ['Simulation und Trace machen Netzverhalten nachvollziehbar', 'Simulation zeigt Verhalten, Trace zeigt den Nachweis'],
  ['Simulation erzeugt reproduzierbares Verhalten; Trace und Findings zeigen, was passiert ist und warum.', 'Simulation erzeugt reproduzierbares Verhalten. Trace und Befunde zeigen, was passiert ist und warum.'],
  ['Lokale KI bleibt an Projektdaten und Fachlogik rückgebunden', 'Lokale KI arbeitet mit Projektwissen und Fachlogik'],
  ['Lokale Modelle erhalten nur den relevanten Projektkontext und bleiben an Modell, Evidence und Regeln gebunden.', 'Lokale Modelle erhalten nur den relevanten Projektkontext und bleiben an Modell, Nachweisen und Regeln gebunden.'],
  ['Qualität endet nicht beim Finden eines Fehlers', 'Qualität beginnt beim Finden und endet beim Nachweis'],
  ['Jeder bestätigte Defekt wird bis zur Reparatur, Regression und objektiven Evidence geführt.', 'Jeder bestätigte Fehler wird repariert, erneut geprüft und mit einem objektiven Nachweis geschlossen.'],
  ['Der Tool Checker bündelt den kompletten Testlauf', 'Der Tool Checker prüft den gesamten Ablauf'],
  ['Die Lücke S41–S50 wird geschlossen: Wizard-Systemprüfungen ergänzen Trace und Agent.', '80 reale Prüfungen decken Fachlogik, Oberfläche, Trace, Wizards und Agent ab.'],
  ['NIS wird zu einer konsistenten Engineering-Plattform', 'Die wichtigsten Bausteine in einem Überblick'],
  ['Die neue Struktur ordnet Skills, Architektur, Datenmodell, Simulation und Qualität in eine klare Erzählung.', 'Die Plattform verbindet Modell, KI, Simulation und Qualität in einem nachvollziehbaren Ablauf.'],
  ['Drei Einsatzfelder decken den gesamten Lebenszyklus ab', 'Wo NIS eingesetzt werden kann'],
  ['NIS unterstützt Entwicklung, Absicherung und Betrieb auf einer gemeinsamen Datenbasis.', 'Ein gemeinsames Modell begleitet Entwicklung, Absicherung und Betrieb.'],
  ['NIS verbindet Modell, KI und Qualität in einem System', 'Die drei wichtigsten Aussagen'],
  ['Die Plattform reduziert Komplexität auf drei belastbare Prinzipien.', 'Drei Prinzipien machen die Plattform verständlich und beherrschbar.'],
  ['Das Ergebnis: schnellere Entscheidungen und nachvollziehbare Qualität.', 'Das Ergebnis: technische Entscheidungen werden schneller und ihre Qualität bleibt nachvollziehbar.'],
]);

let changed = 0;
for (const slide of presentation.slides.items) {
  for (const shape of (slide.shapes?.items ?? [])) {
    let text = '';
    try { text = shape.text?.toString?.() ?? ''; } catch {}
    if (!text) continue;
    for (const [oldText, newText] of replacements) {
      if (text.includes(oldText)) {
        shape.text = text.replace(oldText, newText);
        changed++;
        text = text.replace(oldText, newText);
      }
    }
  }
}

const candidatePath = path.join(stagingDir, 'candidate.pptx');
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
const { finalizePresentation } = await import(pathToFileURL(path.join(SKILL_DIR, 'container_tools/artifact_tool_utils.mjs')).href);
const result = await finalizePresentation({
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: 'C:/Users/marti/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
  integrityValidatorPath: path.join(SKILL_DIR, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(SKILL_DIR, 'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit'],
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, 'validation-v2.json'),
});
console.log(JSON.stringify({ changed, finalPath, result }, null, 2));
