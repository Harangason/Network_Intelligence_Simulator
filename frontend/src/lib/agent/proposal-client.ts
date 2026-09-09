import type { EngineeringProposal } from "./engineering-agent";

type ProposalStatus = Partial<EngineeringProposal> & Pick<EngineeringProposal, "proposal_id" | "revision" | "status">;

export function hasCompleteProposal(value: Partial<EngineeringProposal>): value is EngineeringProposal {
  return value.content_state !== "REFERENCE" && Array.isArray(value.changes)
    && (value.change_count === undefined || value.change_count === value.changes.length)
    && value.changes.every(change => change && typeof change === "object" && typeof change.action === "string" && typeof change.object_type === "string")
    && Array.isArray(value.assumptions) && value.assumptions.every(item => typeof item === "string")
    && Array.isArray(value.canonical_ids) && value.canonical_ids.every(item => item && typeof item === "object" && typeof item.id === "string")
    && Boolean(value.validation_result && typeof value.validation_result === "object") && typeof value.rationale === "string";
}

export const PROPOSAL_PAGE_SIZE = 50;
export function proposalChangePage(proposal: EngineeringProposal, page: number) {
  const pages = Math.max(1, Math.ceil(proposal.changes.length / PROPOSAL_PAGE_SIZE));
  const current = Math.max(0, Math.min(Math.floor(page), pages - 1));
  const offset = current * PROPOSAL_PAGE_SIZE;
  return { page: current, pages, offset, changes: proposal.changes.slice(offset, offset + PROPOSAL_PAGE_SIZE) };
}

async function readResult(response: Response): Promise<ProposalStatus> {
  const result = await response.json();
  if (!response.ok || !result.success || !result.data?.proposal_id) {
    throw new Error(result.error ?? result.findings?.[0]?.message ?? "Vorschlag konnte nicht gelesen werden.");
  }
  return result.data;
}

/** Never attach a replacement's approval status to the old proposal's content. */
export async function refreshProposal(
  current: EngineeringProposal, projectId: string, signal?: AbortSignal, requireFull = false,
): Promise<EngineeringProposal> {
  const options = { headers: { "X-Project-ID": projectId }, cache: "no-store" as const, signal };
  const base = "/api/engineering/agent/proposals/";
  const status = await readResult(await fetch(`${base}${encodeURIComponent(current.proposal_id)}?view=status`, options));
  if (!requireFull && hasCompleteProposal(current) && status.proposal_id === current.proposal_id && status.revision === current.revision) {
    return { ...current, ...status, canonical_count: status.canonical_ids?.length ?? current.canonical_count };
  }
  const full = await readResult(await fetch(`${base}${encodeURIComponent(status.proposal_id)}`, options));
  if (full.proposal_id !== status.proposal_id || !hasCompleteProposal(full)) {
    throw new Error("Die neue Vorschlagsfassung ist noch nicht vollständig geladen.");
  }
  return { ...full, content_state: "FULL", change_count: full.changes.length, canonical_count: full.canonical_ids.length };
}

/** A lost response does not imply a lost commit. Read back, never repeat the POST. */
export async function applyReviewedProposal(
  proposal: EngineeringProposal, projectId: string, csrfToken: string,
): Promise<EngineeringProposal> {
  try {
    const result = await readResult(await fetch(
      `/api/engineering/agent/proposals/${encodeURIComponent(proposal.proposal_id)}/apply?view=status`,
      { method: "POST", headers: { "Content-Type": "application/json", "X-Project-ID": projectId,
        "X-Review-CSRF": csrfToken, "X-Human-Review": "confirmed" },
        body: JSON.stringify({ revision: proposal.revision }) },
    ));
    return { ...proposal, ...result, canonical_count: result.canonical_ids?.length ?? proposal.canonical_count };
  } catch (cause) {
    try {
      const persisted = await refreshProposal(proposal, projectId);
      if (persisted.proposal_id === proposal.proposal_id && persisted.status === "APPLIED") return persisted;
    } catch { /* Preserve the uncertain write outcome; do not invent success. */ }
    const detail = cause instanceof Error && !/fetch|network|load failed/i.test(cause.message)
      ? ` ${cause.message}` : "";
    throw new Error(`Übernahme nicht bestätigt. Der gespeicherte Stand wird beim nächsten Abruf erneut geprüft; bitte nicht blind wiederholen.${detail}`);
  }
}

/** One explicit wizard review performs both governed transitions atomically. */
export async function approveAndApplyWizardProposal(
  proposal: EngineeringProposal, projectId: string, csrfToken: string,
): Promise<EngineeringProposal> {
  try {
    const result = await readResult(await fetch(
      `/api/engineering/agent/proposals/${encodeURIComponent(proposal.proposal_id)}/approve-apply?view=status`,
      { method: "POST", headers: { "Content-Type": "application/json", "X-Project-ID": projectId,
        "X-Review-CSRF": csrfToken, "X-Human-Review": "confirmed" },
        body: JSON.stringify({ revision: proposal.revision }) },
    ));
    return { ...proposal, ...result, canonical_count: result.canonical_ids?.length ?? proposal.canonical_count };
  } catch (cause) {
    try {
      const persisted = await refreshProposal(proposal, projectId);
      if (persisted.proposal_id === proposal.proposal_id && persisted.status === "APPLIED") return persisted;
    } catch { /* Preserve the uncertain write outcome; do not invent success. */ }
    const detail = cause instanceof Error && !/fetch|network|load failed/i.test(cause.message)
      ? ` ${cause.message}` : "";
    throw new Error(`Freigabe und Übernahme nicht bestätigt. Der gespeicherte Stand wird beim nächsten Abruf erneut geprüft; bitte nicht blind wiederholen.${detail}`);
  }
}
