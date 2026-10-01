import { z } from "zod";
import { outputEnvelopeSchema } from './input-output.ts';

export const chatMessageTypes = ["TEXT", "QUESTION", "MULTI_SELECT", "SINGLE_SELECT", "RECOMMENDATION", "FINDING", "PROGRESS", "RESULT", "APPROVAL", "ERROR"] as const;
export const interactiveOptionSchema = z.object({
  id: z.string().min(1).max(200), label: z.string().min(1).max(300), description: z.string().default(""),
  recommended: z.boolean().default(false), disabled: z.boolean().default(false), reason: z.string().default(""),
  metadata: z.record(z.string(), z.unknown()).default({}),
}).strict();
export const interactiveQuestionSchema = z.object({
  id: z.string().min(1), question: z.string().min(1), description: z.string().default(""),
  selection_mode: z.enum(["SINGLE", "MULTI"]), options: z.array(interactiveOptionSchema).min(2).max(8),
  recommended_options: z.array(z.string()).default([]), required: z.boolean().default(true),
  engineering_impact: z.enum(["OPTIONAL", "REQUIRED", "CRITICAL"]).default("REQUIRED"),
  context_refs: z.array(z.record(z.string(), z.string())).default([]),
  status: z.enum(["OPEN", "ANSWERED", "SKIPPED", "EXPIRED", "OUTDATED"]).default("OPEN"),
}).strict().superRefine((q, ctx) => {
  const ids = q.options.map(o => o.id);
  const recommended = q.recommended_options.length ? q.recommended_options : q.options.filter(o => o.recommended).map(o => o.id);
  if (new Set(ids).size !== ids.length || recommended.some(id => !q.options.some(o => o.id === id && !o.disabled)) || (q.selection_mode === "SINGLE" && recommended.length > 1))
    ctx.addIssue({ code: "custom", message: "Ungültige Auswahloptionen" });
});
export const agentResponseSchema = z.object({
  outputs: z.array(outputEnvelopeSchema).max(20).default([]),
  id: z.string().min(1), type: z.enum(chatMessageTypes), text: z.string().max(30000).default(""), title: z.string().max(300).default(""),
  context_refs: z.array(z.record(z.string(), z.string())).max(100).default([]), question: interactiveQuestionSchema.optional(),
  options: z.array(interactiveOptionSchema).default([]), actions: z.array(z.record(z.string(), z.unknown())).max(12).default([]),
  findings: z.array(z.record(z.string(), z.unknown())).max(100).default([]), progress: z.array(z.record(z.string(), z.string())).max(20).default([]),
  recommendation: z.record(z.string(), z.unknown()).optional(), approval: z.record(z.string(), z.unknown()).optional(),
  metadata: z.record(z.string(), z.unknown()).default({}), created_at: z.string().min(1),
  proposal: z.object({ proposal_id: z.string(), proposal_type: z.string(), revision: z.string(),
    status: z.enum(['PROPOSED','VALIDATED','REJECTED','APPROVED','APPLIED','OUTDATED']), rationale: z.string(), assumptions: z.array(z.string()),
    changes: z.array(z.object({action:z.string(),object_type:z.string(),data:z.record(z.string(),z.unknown()).optional()}).passthrough()).max(10000),
    validation_result:z.object({findings:z.array(z.object({message:z.string()}).passthrough()).optional()}).passthrough(),
    canonical_ids:z.array(z.object({object_type:z.string(),id:z.string()})),
  }).passthrough().optional(), workload: z.record(z.string(), z.unknown()).optional(),
  status: z.string().default(""), severity: z.string().default(""),
}).strict().superRefine((event, ctx) => {
  if (["QUESTION", "SINGLE_SELECT", "MULTI_SELECT"].includes(event.type) && !event.question)
    ctx.addIssue({ code: "custom", message: "Strukturierte Frage fehlt" });
});
export type InteractiveQuestion = z.infer<typeof interactiveQuestionSchema>;
export type AgentInput = { type: "QUESTION_ANSWER" | "SKIP_QUESTION"; question_id: string; selected_options: string[] } | { type: 'RESUME' } | { type: 'FINDING_ACTION'; finding_id: string };
export function parseAgentResponse(value: unknown) {
  const parsed = agentResponseSchema.safeParse(value);
  if (parsed.success) return parsed.data;
  console.warn("Invalid engineering AgentResponse; TEXT fallback", parsed.error.issues.map(issue => issue.path.join(".")));
  return agentResponseSchema.parse({ id: crypto.randomUUID(), type: "TEXT", text: "Die Antwort konnte nicht als Engineering-Karte dargestellt werden. Bitte die Anfrage präzisieren.", created_at: new Date().toISOString(), metadata: { contract_error: true } });
}
