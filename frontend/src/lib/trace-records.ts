export type TraceSignal = { id: string; name: string; value: number | string | boolean | null; unit: string; quality: string };
export type TraceEvent = {
  id: string; timestamp: number; source: string; destination: string; technology: string;
  payload: string; message: string; signal: string; value: number | null; status: string;
  finding: string; unit: string; refs: Record<string, string>[]; signals: TraceSignal[];
  ipContext: string;
};
export const MAX_IMPORT_BYTES = 5 * 1024 * 1024;

function recordObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Ein Trace-Ereignis muss ein JSON-Objekt sein.');
  return value as Record<string, unknown>;
}

export function eventFromRecord(value: unknown, index: number): TraceEvent {
  const record = recordObject(value);
  const rawTime = record.timestamp_s ?? record.time_s ?? record.timestamp ?? record.t;
  const timestamp = typeof rawTime === 'number' || typeof rawTime === 'string' && rawTime.trim() ? Number(rawTime) : NaN;
  if (!Number.isFinite(timestamp) || timestamp < 0) throw new Error(`Ereignis ${index + 1}: gültiger Zeitstempel in Sekunden fehlt.`);
  let rawSignals = record.signals;
  if (typeof rawSignals === 'string' && rawSignals.trim()) rawSignals = JSON.parse(rawSignals);
  const candidates = Array.isArray(rawSignals) ? rawSignals : record.signal || record.signal_name ? [record] : [];
  const signals: TraceSignal[] = candidates.slice(0, 64).map((raw, signalIndex) => {
    const item = recordObject(raw);
    const rawValue = item.value ?? item.signal_value;
    return { id: String(item.signal_id ?? item.signal ?? item.signal_name ?? signalIndex),
      name: String(item.signal ?? item.signal_name ?? item.name ?? item.signal_id ?? signalIndex),
      value: typeof rawValue === 'number' || typeof rawValue === 'string' || typeof rawValue === 'boolean' ? rawValue : null,
      unit: String(item.unit ?? ''), quality: String(item.quality ?? item.status ?? '') };
  });
  const first = signals[0];
  const source = String(record.source_name ?? record.sender_hardware ?? record.source ?? record.sender ?? record.from ?? record.node ?? '-')
    + (record.source_logical_address ? ` (${record.source_logical_address})` : '');
  const addresses = Array.isArray(record.destination_logical_addresses) ? record.destination_logical_addresses.filter(Boolean) : [];
  const destination = String(record.destination_names ?? record.receiver_hardware ?? record.destination ?? record.receiver ?? record.to ?? record.target ?? '-')
    + (addresses.length ? ` (${addresses.join(', ')})` : '');
  const message = String(record.message_ids ?? record.message_id ?? record.message ?? record.route_id ?? record.frame_id ?? record.id ?? `event-${index + 1}`);
  const rawValue = first?.value ?? record.value ?? record.signal_value;
  const numberValue = rawValue === null || rawValue === undefined || rawValue === '' ? NaN : Number(rawValue);
  const refs = [
    ['HardwareNode', record.sender_hardware], ['Route', record.route_ref], ['Function', record.function_ref],
    ['Message', Array.isArray(record.message_ids) ? record.message_ids[0] : record.message_id],
    ...candidates.slice(0, 64).map(item => ['Signal', recordObject(item).signal_id]),
  ].filter(([, id]) => typeof id === 'string' && id).map(([object_type, id]) => ({ object_type: String(object_type), id: String(id) }));
  let rawEthernet = record.ethernet;
  if (typeof rawEthernet === 'string' && rawEthernet.trim()) rawEthernet = JSON.parse(rawEthernet);
  const ethernet = rawEthernet && typeof rawEthernet === 'object' ? rawEthernet as Record<string, unknown> : null;
  const ipSource = ethernet?.source as Record<string, unknown> | undefined;
  const ipTargets = Array.isArray(ethernet?.destinations) ? ethernet.destinations as Record<string, unknown>[] : [];
  const ipEndpoint = (ip: unknown, port: unknown) => `${String(ip).includes(':') ? `[${ip}]` : ip}:${port}`;
  const ipContext = ethernet ? `IPv${ethernet.ip_version} / ${String(ethernet.transport_protocol).toUpperCase()} · TX ${ipSource?.port_id}: ${ipEndpoint(ipSource?.ip, ethernet.source_port)} → RX ${ipTargets.map((target, i) => `${target.port_id}: ${ipEndpoint(target.ip, Array.isArray(ethernet.destination_ports) ? ethernet.destination_ports[i] : '')}`).join(', ')}${ipSource?.ip_provenance === 'simulation_derived' || ipTargets.some(target => target.ip_provenance === 'simulation_derived') ? ' · Simulationsadressen (abgeleitet)' : ''}` : '';
  return { id: `${record.route_id ?? message}-${record.sequence ?? index}-${index}`, timestamp, source, destination,
    technology: String(record.technology ?? record.bus ?? record.channel ?? 'trace'),
    payload: String(record.payload_hex ?? record.payload ?? record.data ?? ''), message,
    signal: first?.name ?? String(record.signal ?? record.signal_name ?? '-'),
    value: Number.isFinite(numberValue) ? numberValue : null,
    status: String(record.status ?? 'observed'),
    finding: String(record.finding ?? record.warning ?? (Array.isArray(record.faults) ? record.faults.join(', ') : record.faults ?? '')),
    unit: first?.unit ?? String(record.unit ?? ''), refs, signals, ipContext };
}

/** RFC-style quoted text fields, including commas, escaped quotes and newlines. */
function csvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], field = '', quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (char === '"') {
      if (quoted && text[index + 1] === '"') { field += '"'; index += 1; }
      else if (quoted || field === '') quoted = !quoted;
      else throw new Error('Ungültiges Anführungszeichen im CSV-Trace.');
    } else if (char === ',' && !quoted) { row.push(field); field = ''; }
    else if ((char === '\n' || char === '\r') && !quoted) {
      row.push(field); if (row.some(item => item.trim())) rows.push(row);
      row = []; field = ''; if (char === '\r' && text[index + 1] === '\n') index += 1;
      if (rows.length === 2001) return rows;
    } else field += char;
  }
  if (quoted) throw new Error('Nicht geschlossenes CSV-Textfeld.');
  row.push(field); if (row.some(item => item.trim())) rows.push(row);
  return rows;
}

export function parseTraceText(text: string): TraceEvent[] {
  if (new TextEncoder().encode(text).byteLength > MAX_IMPORT_BYTES) throw new Error('Lokaler Trace-Import: maximal 5 MiB.');
  const trimmed = text.replace(/^\uFEFF/, '').trim();
  if (!trimmed) return [];
  if (trimmed.startsWith('[')) {
    const rows = JSON.parse(trimmed);
    if (!Array.isArray(rows)) throw new Error('Ein JSON-Array mit Ereignissen wird erwartet.');
    return rows.slice(0, 2000).map(eventFromRecord);
  }
  if (trimmed.startsWith('{')) {
    let document: unknown;
    try { document = JSON.parse(trimmed); } catch { /* Multiple JSONL records are parsed individually below. */ }
    if (document) {
      const record = recordObject(document);
      return (Array.isArray(record.events) ? record.events.slice(0, 2000) : [record]).map(eventFromRecord);
    }
    return trimmed.split(/\r?\n/).filter(line => line.trim()).slice(0, 2000).map((line, index) => eventFromRecord(JSON.parse(line), index));
  }
  const [headers, ...rows] = csvRows(trimmed);
  if (!headers?.some(header => ['timestamp_s', 'time_s', 'timestamp', 't'].includes(header.trim()))) {
    throw new Error('CSV-Trace benötigt eine Zeitspalte (z. B. time_s).');
  }
  return rows.slice(0, 2000).map((row, index) => {
    if (row.length !== headers.length) throw new Error(`CSV-Zeile ${index + 2}: Spaltenzahl stimmt nicht.`);
    return eventFromRecord(Object.fromEntries(headers.map((header, column) => [header.trim(), row[column]])), index);
  });
}
