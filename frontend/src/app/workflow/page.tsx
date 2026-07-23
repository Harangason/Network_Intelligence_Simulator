import Link from "next/link";
import { Arrow, MarketingShell, PageHero } from "@/components/marketing-shell";

const steps = [
  { index: "01", label: "Configure", title: "Choose the system boundary.", text: "Wähle Anwendungsbereich und Protokoll. Lege Knoten, Timing, Payload, Bitrate und Fehlerwahrscheinlichkeiten fest.", command: "domain: automotive\nprotocol: can_fd\nnodes: 12" },
  { index: "02", label: "Validate", title: "Catch limits before runtime.", text: "Die Vorabprüfung erkennt ungültige Parameter und Hardwarekonflikte, bevor Simulationsdaten erzeugt werden.", command: "validation: passed\nlimits: 6 checked\nfindings: 0" },
  { index: "03", label: "Simulate", title: "Create a reproducible trace.", text: "Ein Seed macht jeden Lauf wiederholbar. Eventgrenzen verhindern unkontrollierte Datenmengen.", command: "seed: 42\nevents: 8,402\nstatus: completed" },
  { index: "04", label: "Inspect & export", title: "Take the evidence with you.", text: "Untersuche Kennzahlen und lade maschinenlesbare Artefakte für Analyse, Tests und Dokumentation herunter.", command: "trace.jsonl\nmetrics.csv\nreport.native" },
];

export default function WorkflowPage() {
  return (
    <MarketingShell>
      <PageHero eyebrow="Built for iteration" title="From question" accent="to verified trace." description="Ein klarer Ablauf reduziert Reibung zwischen Systemidee, technischer Prüfung und auswertbarem Ergebnis." />
      <section className="workflow-steps">
        {steps.map((step) => <article className="workflow-step" key={step.index}><div className="step-index">{step.index}</div><div><p className="section-label">{step.label}</p><h2>{step.title}</h2><p>{step.text}</p></div><pre><code>{step.command}</code></pre></article>)}
      </section>
      <section className="page-cta"><p className="section-label">Try the complete flow</p><h2>Your first trace is one configuration away.</h2><Link className="primary-link" href="/studio">Start workflow <Arrow /></Link></section>
    </MarketingShell>
  );
}
