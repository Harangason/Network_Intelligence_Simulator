import { SettingsPanel } from "@/components/settings-panel";
import { StudioTopbar } from "@/components/studio-topbar";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/lib/user-settings";

export default async function SettingsPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const initialProjectId = projectIdFromSearchParams(await searchParams);
  return (
    <main className="shell studio-shell">
      <StudioTopbar initialProjectId={initialProjectId} />
      <section className="settings-heading">
        <p className="eyebrow">Einstellungen</p>
        <h1>Systemeinstellungen</h1>
      </section>
      <SettingsPanel />
    </main>
  );
}
