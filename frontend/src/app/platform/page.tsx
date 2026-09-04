import { Arrow, MarketingShell, PageHero, ProjectAwareLink } from "@/components/marketing-shell";

const capabilities = [
  ["01", "Model", "Definiere Knoten, Bitraten, Payloads, Zyklen und Fehlerraten für reproduzierbare Szenarien."],
  ["02", "Validate", "Prüfe Konfigurationen gegen Payload-, Event- und Hardwaregrenzen, bevor ein Trace entsteht."],
  ["03", "Simulate", "Erzeuge deterministische Ereignisse für CAN, Ethernet, Funk, industrielle Netze und mehr."],
  ["04", "Export", "Lade universelle JSONL- und CSV-Daten oder technologiespezifische native Artefakte herunter."],
];

const families = ["Automotive", "Industrial", "Aerospace", "IoT", "Telecom", "Energy", "Robotics", "Medical"];

export default function PlatformPage() {
  return (
    <MarketingShell>
      <PageHero eyebrow="The platform" title="One workspace." accent="Every signal." description="Modelliere, validiere und untersuche Kommunikationssysteme in einer durchgängigen Umgebung — technologieoffen und reproduzierbar." />
      <section className="subpage-section">
        <div className="capability-grid">
          {capabilities.map(([index, title, text]) => (
            <article className="capability-card" key={index}><span>{index}</span><h2>{title}</h2><p>{text}</p></article>
          ))}
        </div>
      </section>
      <section className="split-feature">
        <div><p className="section-label">Broad by design</p><h2>Von Embedded Bus bis Wide Area Network.</h2><p>Die Plattform abstrahiert gemeinsame Netzwerkparameter, ohne technologiespezifische Grenzen zu verstecken.</p></div>
        <div className="family-list">{families.map((family, index) => <div key={family}><span>{String(index + 1).padStart(2, "0")}</span><strong>{family}</strong><i>Supported</i></div>)}</div>
      </section>
      <section className="page-cta"><p className="section-label">Start with a real system</p><h2>Turn a configuration into evidence.</h2><ProjectAwareLink className="primary-link" href="/studio">Open studio <Arrow /></ProjectAwareLink></section>
    </MarketingShell>
  );
}
