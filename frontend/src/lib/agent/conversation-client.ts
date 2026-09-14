/** Deduplicate polling by all visible cards without sharing state across projects. */
import type { InteractiveQuestion } from './agent-response';
type ConversationSnapshot = { success: boolean; data: {
  questions: Record<string, InteractiveQuestion & { selected_options?: string[]; decision_key?: string }>;
  selected_context: { active_view: string; selected_object_refs: Record<string, string>[] };
  decisions: Record<string, { status: string; rationale: string; review_on_change: boolean }>;
} };
const pending = new Map<string, { expires: number; promise: Promise<ConversationSnapshot> }>();
export async function readConversation(projectId: string, signal?: AbortSignal, questionId?: string): Promise<ConversationSnapshot> {
  let entry = pending.get(projectId);
  if (!entry || entry.expires < Date.now()) {
    const promise = fetch('/api/engineering/agent/conversation', {
      headers: { 'X-Project-ID': projectId }, cache: 'no-store', signal: AbortSignal.timeout(8000),
    }).then(async response => {
      if (!response.ok) throw new Error('Gesprächsstand vorübergehend nicht verfügbar.');
      const result = await response.json() as ConversationSnapshot;
      if (!result.success || !result.data) throw new Error('Gesprächsstand konnte nicht geladen werden.');
      return result;
    });
    entry = { expires: Infinity, promise };
    pending.set(projectId, entry);
    const current = entry;
    void promise.then(() => { current.expires = Date.now() + 1000; }, () => { if (pending.get(projectId) === current) pending.delete(projectId); });
    if (pending.size > 20) pending.delete(pending.keys().next().value!);
  }
  const result = await entry.promise;
  signal?.throwIfAborted();
  if (questionId && !result.data.questions[questionId]) {
    if (pending.get(projectId) === entry) pending.delete(projectId);
    return readConversation(projectId, signal);
  }
  return result;
}
