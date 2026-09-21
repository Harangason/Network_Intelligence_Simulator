export type SequenceSource = "SIMULATED" | "OBSERVED";

export type SequenceEvent = {
  id: string;
  transactionId: string | null;
  timeS: number | null;
  source: string;
  destination: string;
  technology: string;
  route: string;
  status: string;
  segmentIndex: number | null;
  segmentCount: number | null;
  releaseTimeS: number | null;
  transportLatencyMs: number | null;
  queueDelayMs: number | null;
  payloadBytes: number | null;
};

export type SequenceDiagramModel = {
  source: SequenceSource;
  participants: string[];
  events: SequenceEvent[];
  transactions: Array<{ id: string; eventIds: string[]; technologies: string[]; complete: boolean }>;
  correlatedCount: number;
  uncorrelatedCount: number;
};

function numberOrNull(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function name(value: unknown, fallback: string): string {
  if (Array.isArray(value)) return value.length ? String(value[0]) : fallback;
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

export function buildSequenceDiagram(records: Record<string, unknown>[], source: SequenceSource): SequenceDiagramModel {
  const events = records.map((record, index): SequenceEvent => {
    const timeS = record.time_status === "unavailable" ? null : numberOrNull(record.time_s);
    const releaseTimeS = numberOrNull(record.origin_release_time_s);
    const final = record.final_segment === true || record.final_segment === "True" || record.final_segment === "true";
    const status = name(record.status, "observed");
    return {
      id: name(record.event_id, `${source}:${index}`),
      transactionId: record.transaction_id || record.end_to_end_event_id ?
        String(record.transaction_id || record.end_to_end_event_id) : null,
      timeS,
      source: name(record.source_name ?? record.sender_hardware ?? record.sender ?? record.source, "Unbekannt"),
      destination: name(record.destination_names ?? record.receiver_hardware ?? record.receivers ?? record.destination, "Unbekannt"),
      technology: name(record.technology ?? record.bus ?? record.channel, "Unbekannt"),
      route: name(record.route_name ?? record.route_id ?? record.message, "Unbekannt"),
      status,
      segmentIndex: numberOrNull(record.segment_index),
      segmentCount: numberOrNull(record.segment_count),
      releaseTimeS,
      transportLatencyMs: final && status === "transmitted" && timeS !== null && releaseTimeS !== null
        ? Math.max(0, (timeS - releaseTimeS) * 1000) : null,
      queueDelayMs: numberOrNull(record.queue_delay_ms),
      payloadBytes: numberOrNull(record.payload_bytes),
    };
  }).sort((left, right) => (left.timeS ?? Infinity) - (right.timeS ?? Infinity));
  const participants = [...new Set(events.flatMap(event => [event.source, event.destination]))];
  const grouped = new Map<string, SequenceEvent[]>();
  for (const event of events) {
    if (!event.transactionId) continue;
    grouped.set(event.transactionId, [...(grouped.get(event.transactionId) ?? []), event]);
  }
  const transactions = [...grouped].map(([id, items]) => ({
    id, eventIds: items.map(item => item.id), technologies: [...new Set(items.map(item => item.technology))],
    complete: items.some(item => item.transportLatencyMs !== null) &&
      items.every(item => item.status === "transmitted"),
  }));
  return { source, participants, events, transactions,
    correlatedCount: events.filter(event => event.transactionId !== null).length,
    uncorrelatedCount: events.filter(event => event.transactionId === null).length };
}
