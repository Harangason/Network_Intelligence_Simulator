import { z } from 'zod';

export const visualizationSchema = z.object({
  visualization_type: z.enum(['NETWORK_DIAGRAM', 'TABLE']), purpose: z.string(), source_revision: z.string(),
  nodes: z.array(z.object({id: z.string(), label: z.string(), object_type: z.string()}).strict()).max(200).default([]),
  relationships: z.array(z.object({source: z.string(), target: z.string(), label: z.string().default(''), evidence_ref: z.string()}).strict()).max(400).default([]),
  columns: z.array(z.string()).max(12).default([]), rows: z.array(z.array(z.string())).max(200).default([]),
  total_objects: z.number().int().nonnegative().default(0), truncated: z.boolean().default(false),
}).strict().superRefine((view, ctx) => {
  const ids = new Set(view.nodes.map(node => node.id));
  if (ids.size !== view.nodes.length || view.relationships.some(edge => !ids.has(edge.source) || !ids.has(edge.target)) || view.rows.some(row => row.length !== view.columns.length))
    ctx.addIssue({code: 'custom', message: 'Ungültige Visualisierungsbezüge'});
});
export const outputEnvelopeSchema = z.object({
  schema_version: z.literal(1).default(1), output_id: z.string(),
  output_type: z.enum(['CHAT', 'QUESTION', 'MODEL_CHANGE', 'FINDING', 'PROPOSAL', 'TABLE', 'GRAPH', 'DIAGRAM', 'CHART', 'TRACE_VIEW', 'FILE', 'REPORT', 'CODE', 'SIMULATION', 'MCP_RESPONSE', 'CALCULATION', 'VALIDATION', 'VISUALIZATION']),
  status: z.string(), project_ref: z.string(), run_ref: z.string(), content: z.string().default(''),
  affected_objects: z.array(z.string()).max(500).default([]), evidence_refs: z.array(z.string()).max(500).default([]),
  visualization: visualizationSchema.optional(), validation: z.record(z.string(), z.unknown()).default({}),
  provenance: z.record(z.string(), z.unknown()).default({}),
}).strict();
export type AgentOutputEnvelope = z.infer<typeof outputEnvelopeSchema>;
export type VisualizationRequest = z.infer<typeof visualizationSchema>;

/** Coordinates express diagram layout, never a physical installation position. */
export function diagramPositions(view: VisualizationRequest) {
  const levels = new Map(view.nodes.map(node => [node.id, 0]));
  const incoming = new Map(view.nodes.map(node => [node.id, 0]));
  for (const edge of view.relationships) incoming.set(edge.target, (incoming.get(edge.target) ?? 0) + 1);
  const queue = view.nodes.filter(node => !incoming.get(node.id)).map(node => node.id);
  for (let i = 0; i < queue.length; i++) {
    for (const edge of view.relationships.filter(edge => edge.source === queue[i])) {
      levels.set(edge.target, Math.max(levels.get(edge.target) ?? 0, (levels.get(edge.source) ?? 0) + 1));
      incoming.set(edge.target, (incoming.get(edge.target) ?? 0) - 1);
      if (!incoming.get(edge.target)) queue.push(edge.target);
    }
  }
  const counts = new Map<number, number>();
  return new Map(view.nodes.map(node => {
    const level = levels.get(node.id) ?? 0;
    const row = counts.get(level) ?? 0;
    counts.set(level, row + 1);
    return [node.id, {x: 20 + level * 210, y: 25 + row * 100}];
  }));
}
