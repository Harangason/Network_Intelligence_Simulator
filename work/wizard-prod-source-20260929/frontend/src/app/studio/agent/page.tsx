import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/lib/user-settings";
import { AgentChatCore } from "@/components/agent-chat-core";
import { StudioTopbar } from "@/components/studio-topbar";
import { EngineeringResponseWorkspace } from '@/components/engineering-response-workspace';
import { ProjectDraftWorkspace } from '@/components/engineering-agent-event';

export default async function AgentPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const params = await searchParams;
  const projectId = projectIdFromSearchParams(params) ?? 'default';
  const responseId = typeof params.response === 'string' ? params.response : undefined;
  const draftId = typeof params.draft === 'string' ? params.draft : undefined;
  const rawBackTo = typeof params.back_to === 'string' ? params.back_to : '';
  let backTo: string | null = null;
  if (rawBackTo.startsWith('/studio/') && !rawBackTo.startsWith('//') && !rawBackTo.includes('\\')) {
    const target = new URL(rawBackTo, 'http://nis.local');
    if (target.origin === 'http://nis.local') {
      target.searchParams.set('project', projectId);
      backTo = `${target.pathname}${target.search}${target.hash}`;
    }
  }
  return <main className="shell studio-shell"><StudioTopbar initialProjectId={projectId} /><section className="engineering-assistant-workspace">
    {backTo && <nav className="engineering-workspace-return"><a className="button secondary" href={backTo}>← Zurück zum geöffneten Projekt</a></nav>}
    <h1>Engineering Assistant</h1><p>Gespräch, Entscheidungen und ausführliche Prüfergebnisse für dieses Projekt.</p>
    {draftId && <ProjectDraftWorkspace projectId={projectId} draftId={draftId} />}
    <EngineeringResponseWorkspace projectId={projectId} responseId={responseId} /><AgentChatCore projectId={projectId} />
  </section></main>;
}
