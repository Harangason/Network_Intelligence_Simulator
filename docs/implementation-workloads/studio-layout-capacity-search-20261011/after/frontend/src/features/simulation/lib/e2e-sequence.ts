export type SequenceSource = "SIMULATED" | "OBSERVED";

/** Read-only boolean search: NOT > AND > OR, with quoted phrases and parentheses. */
export function compileSequenceSearch(query: string): { error: string | null; matches: (event: SequenceEvent) => boolean } {
  type Token = { kind: "TERM" | "AND" | "OR" | "NOT" | "(" | ")"; value: string };
  type Predicate = (fields: string[]) => boolean;
  const text = query.trim();
  const fields = (event: SequenceEvent) => [event.source, event.destination, event.route, event.technology,
    event.status, event.transactionId ?? ""].map(value => value.toLocaleLowerCase());
  const term = (value: string): Predicate => values => values.some(field => field.includes(value.toLocaleLowerCase()));
  if (!text) return { error: null, matches: () => true };
  try {
    if (text.length > 4096) throw new Error("Suchausdruck ist zu lang (maximal 4096 Zeichen).");
    // Preserve the existing literal phrase search when no expression syntax is used.
    if (!/[()"]|(?:^|\s)(?:UND|AND|ODER|OR|NICHT|NOT)(?=\s|$)/i.test(text)) {
      const predicate = term(text);
      return { error: null, matches: event => predicate(fields(event)) };
    }
    const tokens: Token[] = [];
    const operators: Record<string, Token["kind"]> = { UND: "AND", AND: "AND", ODER: "OR", OR: "OR", NICHT: "NOT", NOT: "NOT" };
    let position = 0;
    while (position < text.length) {
      if (/\s/.test(text[position])) { position++; continue; }
      const character = text[position];
      if (character === "(" || character === ")") { tokens.push({ kind: character, value: character }); position++; continue; }
      if (character === '"') {
        position++;
        let value = "", closed = false;
        while (position < text.length) {
          const next = text[position++];
          if (next === '"') { closed = true; break; }
          if (next === "\\" && /["\\]/.test(text[position] ?? "")) value += text[position++];
          else value += next;
        }
        if (!closed) throw new Error("Schließendes Anführungszeichen fehlt.");
        if (!value) throw new Error("Leerer Suchbegriff ist nicht zulässig.");
        tokens.push({ kind: "TERM", value });
        continue;
      }
      const start = position;
      while (position < text.length && !/[\s()"]/.test(text[position])) position++;
      const value = text.slice(start, position);
      tokens.push({ kind: operators[value.toUpperCase()] ?? "TERM", value });
    }
    let cursor = 0;
    function primary(depth: number): Predicate {
      if (depth > 64) throw new Error("Suchausdruck ist zu tief verschachtelt.");
      const token = tokens[cursor++];
      if (!token) throw new Error("Suchbegriff nach dem Operator fehlt.");
      if (token.kind === "NOT") { const operand = primary(depth + 1); return values => !operand(values); }
      if (token.kind === "(") {
        const operand = disjunction(depth + 1);
        if (tokens[cursor++]?.kind !== ")") throw new Error("Schließende Klammer fehlt.");
        return operand;
      }
      if (token.kind !== "TERM") throw new Error(`Suchbegriff vor „${token.value}“ fehlt.`);
      return term(token.value);
    }
    function conjunction(depth: number): Predicate {
      let predicate = primary(depth);
      while (tokens[cursor] && tokens[cursor].kind !== "OR" && tokens[cursor].kind !== ")") {
        if (tokens[cursor].kind === "AND") cursor++;
        const right = primary(depth);
        const left = predicate;
        predicate = values => left(values) && right(values);
      }
      return predicate;
    }
    function disjunction(depth: number): Predicate {
      let predicate = conjunction(depth);
      while (tokens[cursor]?.kind === "OR") {
        cursor++;
        const right = conjunction(depth);
        const left = predicate;
        predicate = values => left(values) || right(values);
      }
      return predicate;
    }
    const predicate = disjunction(0);
    if (cursor !== tokens.length) throw new Error("Unerwartete schließende Klammer.");
    return { error: null, matches: event => predicate(fields(event)) };
  } catch (error) {
    return { error: error instanceof Error ? error.message : "Ungültiger Suchausdruck.", matches: () => false };
  }
}

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

/** Display filter on original hop endpoints; never infer an unobserved connection. */
export function sequenceEventMatchesParticipants(event: SequenceEvent, selected: ReadonlySet<string>): boolean {
  if (selected.size === 0) return true;
  if (selected.size === 1) return selected.has(event.source) || selected.has(event.destination);
  return event.source !== event.destination && selected.has(event.source) && selected.has(event.destination);
}

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
