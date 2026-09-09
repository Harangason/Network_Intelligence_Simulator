import type { EngineeringProposal } from "./engineering-agent";

type ProposalStatus = Partial<EngineeringProposal> & Pick<EngineeringProposal, "proposal_id" | "revision" | "status">;

async function readResult(response: Response): Promise<ProposalStatus> {
  const result = await response.json();
  if (!response.ok || !result.success || !result.data?.proposal_id) {
    throw new Error(result.error ?? result.findings?.[0]?.message ?? "Vorschlag konnte nicht gelesen werden.");
  }
  return result.data;
}

/** Never attach a replacement's approval status to the old proposal's content. */
export async function refreshProposal(
  current: EngineeringProposal, projectId: string, signal?: AbortSignal,
): Promise<EngineeringProposal> {
  const options = { headers: { "X-Project-ID": projectId }, cache: "no-store" as const, signal };
  const base = "/api/engineering/agent/proposals/";
  const status = await readResult(await fetch(`${base}${encodeURIComponent(current.proposal_id)}?view=status`, options));
  if (status.proposal_id === current.proposal_id && status.revision === current.revision) {
    return { ...current, ...status };
  }
  const full = await readResult(await fetch(`${base}${encodeURIComponent(status.proposal_id)}`, options));
  if (!Array.isArray(full.changes) || !Array.isArray(full.assumptions) || !full.rationale) {
    throw new Error("Die neue Vorschlagsfassung ist noch nicht vollständig geladen.");
  }
  return full as EngineeringProposal;
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
    return { ...proposal, ...result };
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
    return { ...proposal, ...result };
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
