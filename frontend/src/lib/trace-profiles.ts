import type { TraceEvent } from './trace-records';
export type TraceColumn = { key: string; label: string; read: (event: TraceEvent) => unknown };
function field(path: string[], label = path.join(' / ')): TraceColumn {
  return { key: path.some(part => part.includes('.')) ? JSON.stringify(path) : path.join('.'), label, read: event => {
    let value: unknown = event.original;
    for (const part of path) value = value && typeof value === 'object' ? (value as Record<string, unknown>)[part] : undefined;
    return value;
  } };
}
const col = (path: string, label: string) => field(path.split('.'), label);
export const TRACE_PROFILES = {
  can: { label: 'CAN / CAN FD', columns: [
    { key: 'can.identifier', label: 'CAN-ID', read: (event: TraceEvent) => {
      const protocols = event.original.protocols as Record<string, Record<string, unknown>> | undefined;
      return protocols?.can?.arbitration_id ?? event.original.arbitration_id
        ?? (/^0x[0-9a-f]+$/i.test(String(event.original.message)) ? event.original.message : undefined);
    } }, col('channel', 'Kanal'), col('dlc', 'DLC'), col('data_length', 'Datenlänge (Byte)'), col('extended_id', 'Extended ID'), col('is_fd', 'CAN FD'), col('bitrate_switch', 'BRS'), col('direction', 'Rx/Tx'), col('status', 'Status')] },
  ethernet: { label: 'Ethernet / IP', columns: [col('source', 'Sender'), col('destination', 'Empfänger'), col('protocols.ethernet.ethertype', 'EtherType'), col('data_length', 'Länge (Byte)'), col('protocols.ip.source', 'Quell-IP'), col('protocols.ip.destination', 'Ziel-IP'), col('protocols.transport.name', 'Transport'), col('protocols.transport.source_port', 'Quellport'), col('protocols.transport.destination_port', 'Zielport')] },
  dds: { label: 'DDS', columns: [col('protocols.dds.topic', 'Topic'), col('protocols.dds.writer_guid', 'Writer GUID'), col('protocols.dds.sequence', 'Sequenznummer')] },
  modbus: { label: 'Modbus', columns: [col('protocols.modbus.unit_id', 'Unit ID'), col('protocols.modbus.function_code', 'Function Code'), col('protocols.modbus.register_address', 'Registeradresse'), col('protocols.modbus.register_count', 'Registeranzahl')] },
  profinet: { label: 'PROFINET', columns: [col('protocols.profinet.frame_id', 'Frame ID'), col('protocols.profinet.cycle_counter', 'Cycle Counter'), col('protocols.profinet.data_status', 'Data Status')] },
  arinc429: { label: 'ARINC 429', columns: [col('protocols.arinc429.label', 'Label'), col('protocols.arinc429.sdi', 'SDI'), col('protocols.arinc429.ssm', 'SSM'), col('protocols.arinc429.parity', 'Parität')] },
  signals: { label: 'Messsignale', columns: [{ key: 'signals', label: 'Messwerte mit Einheiten', read: (event: TraceEvent) => event.signals.map(signal => `${signal.name}: ${signal.value ?? '—'} ${signal.unit}`).join('; ') }] },
  generic: { label: 'Generisch / gemischt', columns: [
    { key: 'generic.message', label: 'Nachricht / Transport Unit', read: (event: TraceEvent) => event.message },
    { key: 'generic.source', label: 'Sender', read: (event: TraceEvent) => event.source },
    { key: 'generic.destination', label: 'Empfänger', read: (event: TraceEvent) => event.destination },
    col('time_basis', 'Zeitbasis'),
  ] },
};
export type TraceProfile = keyof typeof TRACE_PROFILES;
export function eventProfile(event: TraceEvent): TraceProfile {
  const protocols = event.original.protocols as Record<string, unknown> | undefined;
  if (protocols?.can || /^CAN(?:[ _-]?FD)?(?:\s|$)/i.test(event.technology)) return 'can';
  if (protocols?.dds || /^DDS(?:\s|$)/i.test(event.technology)) return 'dds';
  if (protocols?.modbus || /^Modbus(?:[ _-]|$)/i.test(event.technology)) return 'modbus';
  if (protocols?.profinet || /^PROFINET(?:\s|$)/i.test(event.technology)) return 'profinet';
  if (protocols?.arinc429 || /^ARINC[ _-]?429(?:\s|$)/i.test(event.technology)) return 'arinc429';
  if (protocols?.ethernet || /^Ethernet$/i.test(event.technology)) return 'ethernet';
  if (event.signals.length) return 'signals';
  return 'generic';
}
export function automaticProfile(events: TraceEvent[]): TraceProfile {
  const kinds = new Set(events.map(eventProfile));
  return kinds.size === 1 ? [...kinds][0] : 'generic';
}
export function availableColumns(events: TraceEvent[]): TraceColumn[] {
  const fields = new Map<string, TraceColumn>();
  for (const profile of Object.values(TRACE_PROFILES)) for (const column of profile.columns) fields.set(column.key, column);
  function visit(value: unknown, path: string[], depth: number) {
    if (depth > 6) return;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      for (const [key, child] of Object.entries(value)) visit(child, [...path, key], depth + 1);
    } else if (path.length) {
      const column = field(path);
      if (!fields.has(column.key)) fields.set(column.key, column);
    }
  }
  for (const event of events) visit(event.original, [], 0);
  return [...fields.values()].filter(column => events.some(event => column.read(event) !== undefined));
}
export function displayTraceValue(value: unknown): string {
  if (value === undefined || value === null) return '—';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}
