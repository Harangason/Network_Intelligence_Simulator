import { SettingsPanel } from "@/components/settings-panel";
import { StudioTopbar } from "@/components/studio-topbar";

export default function SettingsPage() {
  return (
    <main className="shell studio-shell">
      <StudioTopbar />
      <section className="settings-heading">
        <p className="eyebrow">Einstellungen</p>
        <h1>Systemeinstellungen</h1>
      </section>
      <SettingsPanel />
    </main>
  );
}
