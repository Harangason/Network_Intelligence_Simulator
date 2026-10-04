import { SettingsPanel } from "@/features/settings/ui/settings-panel";
import { SettingsProjectReturnLink } from "@/features/settings/ui/settings-project-return-link";
import { StudioTopbar } from "@/features/workflow/ui/studio-topbar";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/features/settings/lib/user-settings";

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
        <div>
          <p className="eyebrow">Einstellungen</p>
          <h1>Systemeinstellungen</h1>
        </div>
        <SettingsProjectReturnLink initialProjectId={initialProjectId} />
      </section>
      <SettingsPanel />
    </main>
  );
}
