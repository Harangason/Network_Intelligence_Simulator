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
  eventKind: "TRANSPORT" | "RECEIVER";
  receiverStatus: "ACCEPTED" | "REJECTED" | null;
  receiverAcceptTimeS: number | null;
  e2eLatencyMs: number | null;
  dataAgeAtAcceptMs: number | null;
};

export type SequenceDiagramModel = {
  source: SequenceSource;
  participants: string[];
  events: SequenceEvent[];
  transactions: Array<{ id: string; eventIds: string[]; technologies: string[]; complete: boolean; receiverStatus: "ACCEPTED" | "REJECTED" | "NOT_OBSERVED" | "UNVERIFIED"; e2eLatencyMs?: number | null; dataAgeAtAcceptMs?: number | null; deadlineStatus?: string; freshnessStatus?: string; requirementStatus?: string; evidenceEventIds?: string[]; findings?: string[] }>;
  correlatedCount: number;
  uncorrelatedCount: number;
};

/** API sequence models are authoritative; this only narrows visible rows for the current view. */
export function sequenceModelForEventIds(model: SequenceDiagramModel, eventIds: Set<string>): SequenceDiagramModel {
  const events = model.events.filter(event => eventIds.has(event.id));
  const visible = new Set(events.map(event => event.id));
  return {
    ...model,
    events,
    transactions: model.transactions.map(transaction => ({
      ...transaction,
      eventIds: transaction.eventIds.filter(id => visible.has(id)),
    })).filter(transaction => transaction.eventIds.length > 0),
    correlatedCount: events.filter(event => event.transactionId !== null).length,
    uncorrelatedCount: events.filter(event => event.transactionId === null).length,
  };
}

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
    const kind = String(record.event_type ?? "").toUpperCase();
    const action = String(record.receiver_action ?? "").toUpperCase();
    const receiverStatus = String(record.receiver_status ?? "").toUpperCase();
    const accepted = receiverStatus === "ACCEPTED" || action === "ACCEPT" || kind === "RECEIVER_ACCEPTANCE";
    const rejected = receiverStatus === "REJECTED" || action === "REJECT" || kind === "RECEIVER_REJECTION";
    const eventKind = kind === "RECEIVER_ACCEPTANCE" || kind === "RECEIVER_REJECTION" ? "RECEIVER" : "TRANSPORT";
    const acceptTime = accepted ? numberOrNull(record.receiver_accept_time_s) ??
      (kind === "RECEIVER_ACCEPTANCE" ? timeS : null) : null;
    const generationTime = numberOrNull(record.data_generation_time_s);
    const validAcceptTime = acceptTime !== null && releaseTimeS !== null && acceptTime >= releaseTimeS &&
      (eventKind === "RECEIVER" || timeS === null || acceptTime >= timeS) ? acceptTime : null;
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
      transportLatencyMs: final && status === "transmitted" && timeS !== null && releaseTimeS !== null && timeS >= releaseTimeS
        ? (timeS - releaseTimeS) * 1000 : null,
      queueDelayMs: numberOrNull(record.queue_delay_ms),
      payloadBytes: numberOrNull(record.payload_bytes),
      eventKind,
      receiverStatus: rejected ? "REJECTED" : accepted && validAcceptTime !== null ? "ACCEPTED" : null,
      receiverAcceptTimeS: validAcceptTime,
      e2eLatencyMs: validAcceptTime !== null && releaseTimeS !== null ? (validAcceptTime - releaseTimeS) * 1000 : null,
      dataAgeAtAcceptMs: validAcceptTime !== null && generationTime !== null && validAcceptTime >= generationTime
        ? (validAcceptTime - generationTime) * 1000 : null,
    };
  }).sort((left, right) => (left.timeS ?? Infinity) - (right.timeS ?? Infinity));
  const participants = [...new Set(events.flatMap(event => [event.source, event.destination]))];
  const grouped = new Map<string, SequenceEvent[]>();
  for (const event of events) {
    if (!event.transactionId) continue;
    grouped.set(event.transactionId, [...(grouped.get(event.transactionId) ?? []), event]);
  }
  const transactions = [...grouped].map(([id, items]) => ({
    id, eventIds: items.map(item => item.id),
    technologies: [...new Set(items.filter(item => item.eventKind === "TRANSPORT").map(item => item.technology))],
    complete: (() => {
      const hops = items.filter(item => item.eventKind === "TRANSPORT");
      const count = hops[0]?.segmentCount;
      return count !== null && count !== undefined && count > 0 &&
        hops.every(item => item.status === "transmitted" && item.segmentCount === count) &&
        new Set(hops.map(item => item.segmentIndex)).size === count &&
        Array.from({ length: count }, (_, index) => index).every(index => hops.some(item => item.segmentIndex === index)) &&
        hops.some(item => item.transportLatencyMs !== null);
    })(),
    receiverStatus: items.some(item => item.receiverStatus === "REJECTED") ? "REJECTED" as const :
      items.some(item => item.receiverStatus === "ACCEPTED") ? "ACCEPTED" as const : "NOT_OBSERVED" as const,
  }));
  return { source, participants, events, transactions,
    correlatedCount: events.filter(event => event.transactionId !== null).length,
    uncorrelatedCount: events.filter(event => event.transactionId === null).length };
}
