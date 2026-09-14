import { z } from 'zod';
import { interactiveQuestionSchema } from './agent-response.ts';

export const wizardTargets = ['engineering_model', 'routing', 'network_editor', 'parameters', 'capacity_timing', 'validation', 'simulation', 'results_analysis', 'data_science_intelligence'] as const;
const commandId = z.string().min(8).max(120).regex(/^[A-Za-z0-9._-]+$/);
export const wizardCommandSchema = z.object({
  action: z.enum(['START', 'CONTINUE', 'AMEND']),
  run_id: commandId,
  operation_id: commandId,
  request_revision: z.string().max(128).optional(),
  target: z.enum(wizardTargets).optional(),
  wizard_context: z.record(z.string(), z.unknown()).optional(),
  automatic: z.boolean().optional(),
}).strict().superRefine((command, ctx) => {
  if (command.action === 'START' && (!command.target || !command.wizard_context))
    ctx.addIssue({ code: 'custom', message: 'Start benötigt Ziel und bestätigte Wizardvorgaben.' });
});
export type WizardCommand = z.infer<typeof wizardCommandSchema>;
export function parseWizardCommand(value: unknown): WizardCommand {
  return wizardCommandSchema.parse(value);
}

const receiptSchema = z.object({
  accepted: z.literal(true), duplicate: z.boolean(), run_id: z.string().min(1),
  operation_id: z.string().min(1), request_revision: z.string().min(1), target: z.enum(wizardTargets),
});
export type WizardReceipt = z.infer<typeof receiptSchema>;
export function wizardReceipt(event: unknown, runId: string): WizardReceipt | null {
  if (!event || typeof event !== 'object' || (event as Record<string, unknown>).type !== 'CONTEXT') return null;
  const result = receiptSchema.safeParse((event as Record<string, unknown>).wizard_receipt);
  return result.success && result.data.run_id === runId ? result.data : null;
}

export function wizardRequestRevision(context: Record<string, unknown> | undefined, runId: string): string | undefined {
  const request = context?.wizard_request as Record<string, unknown> | undefined;
  return request?.run_id === runId && typeof request.revision === 'string' ? request.revision : undefined;
}

export function wizardContextForRequest(workflow: { project_id?: string; context?: Record<string, unknown> } | null,
  projectId: string, runId: string, requestRevision: string | undefined): Record<string, unknown> | null {
  const request = workflow?.context?.wizard_request as Record<string, unknown> | undefined;
  const wizard = workflow?.context?.agent_wizard_status as Record<string, unknown> | undefined;
  return Boolean(requestRevision) && workflow?.project_id === projectId && request?.run_id === runId
    && request.revision === requestRevision && wizard?.project_id === projectId && wizard.run_id === runId
    && wizard.request_revision === requestRevision ? wizard : null;
}

export function wizardConversationMatches(value: unknown, runId: string) {
  if (!value || typeof value !== 'object' || !runId) return false;
  const conversation = value as Record<string, unknown>;
  const request = conversation.wizard_request as Record<string, unknown> | undefined;
  if (request?.run_id) return request.run_id === runId;
  // Migration support for persisted requests predating the typed command.
  return String(conversation.current_requirement ?? '').split(/\r?\n/)
    .some(line => line.trim().replace(/^-\s*/, '') === `Lauf-ID: ${runId}`);
}

export function wizardQuestionFromConversation(value: unknown, runId: string) {
  if (!wizardConversationMatches(value, runId)) return null;
  const conversation = value as Record<string, unknown>;
  const id = conversation.current_question;
  const questions = conversation.questions as Record<string, unknown> | undefined;
  const stored = typeof id === 'string' ? questions?.[id] : undefined;
  // Conversation records also contain decision/revision/expiry metadata; those
  // fields stay server-owned and are not part of the display contract.
  const display = stored && typeof stored === 'object' ? Object.fromEntries(Object.entries(stored)
    .filter(([key]) => key in interactiveQuestionSchema.shape)) : undefined;
  const result = interactiveQuestionSchema.safeParse(display);
  return result.success && result.data.status === 'OPEN' ? result.data : null;
}
