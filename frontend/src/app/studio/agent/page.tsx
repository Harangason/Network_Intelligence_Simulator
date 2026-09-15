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
  return <main className="shell studio-shell"><StudioTopbar initialProjectId={projectId} /><section className="engineering-assistant-workspace"><h1>Engineering Assistant</h1><p>Gespräch, Engineering-Entscheidungen und ausführliche Prüfergebnisse.</p>{draftId && <ProjectDraftWorkspace projectId={projectId} draftId={draftId} />}<EngineeringResponseWorkspace projectId={projectId} responseId={responseId} /><AgentChatCore projectId={projectId} /></section></main>;
}
