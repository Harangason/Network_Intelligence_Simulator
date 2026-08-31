export type InspectionObject = { id: string; name?: string; [key: string]: unknown };
export type InspectionSources = {
  versions: Record<string, number>;
  topology: Record<string, unknown>;
  hardware: InspectionObject[];
  interfaces: InspectionObject[];
  functions: InspectionObject[];
  messages: InspectionObject[];
  signals: InspectionObject[];
  routes: InspectionObject[];
};
export type SignalCheck = { code: string; severity: "ERROR" | "WARNING" | "OPEN"; text: string };
export type SignalInspection = {
  id: string; name: string; messageId: string; messageName: string;
  bits: number | null; requiredBits: number | null; start: number | null;
  dataType: string; byteOrder: string; min: number | null; max: number | null;
  factor: number | null; offset: number | null; unit: string;
  occupiedBits: number[] | null; checks: SignalCheck[];
  status: "ERROR" | "WARNING" | "OPEN" | "PASS";
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function objects(value: unknown): InspectionObject[] { return Array.isArray(value) ? value as InspectionObject[] : []; }
function strings(value: unknown): string[] { return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && !!item) : []; }
function numeric(value: unknown): number | null { return typeof value === "number" && Number.isFinite(value) ? value : null; }
function text(value: unknown): string { return typeof value === "string" ? value : ""; }
function checkStatus(checks: SignalCheck[]): SignalInspection["status"] {
  return checks.some((item) => item.severity === "ERROR") ? "ERROR"
    : checks.some((item) => item.severity === "OPEN") ? "OPEN"
    : checks.length ? "WARNING" : "PASS";
}
function hasMultiplexing(signal: InspectionObject): boolean {
  return [signal, record(signal.configuration), record(signal.protocol_bindings)].some((source) =>
    Object.entries(source).some(([key, value]) => /multiplex|^mux/.test(key) && value != null && value !== false));
}

export function inspectSignal(signal: InspectionObject, message?: InspectionObject): SignalInspection {
  const checks: SignalCheck[] = [];
  const add = (code: string, severity: SignalCheck["severity"], text: string) => checks.push({ code, severity, text });
  const bits = numeric(signal.length_bits), start = numeric(signal.start_bit);
  const min = numeric(signal.min_value), max = numeric(signal.max_value);
  const factor = numeric(signal.factor), offset = numeric(signal.offset_value);
  const dataType = text(signal.data_type).toLowerCase();
  const byteOrder = text(signal.byte_order);
  const dlc = numeric(message?.dlc);
  const validBits = bits !== null && Number.isInteger(bits) && bits > 0 && bits <= 65536;
  const validStart = start !== null && Number.isInteger(start) && start >= 0 && start <= 65536;
  if (!validBits) add("BIT_LENGTH", bits === null ? "OPEN" : "ERROR", "Gültige Bitlänge fehlt (1 bis 65536 Bit).");
  if (!validStart) add("START_BIT", start === null ? "OPEN" : "ERROR", "Gültige Startposition fehlt.");
  if (!["little_endian", "big_endian"].includes(byteOrder)) add("BYTE_ORDER", "OPEN", "Byte-Reihenfolge ist nicht definiert.");
  if (!message) add("MESSAGE_MISSING", "OPEN", "Zugeordnete Nachricht fehlt; Payload-Prüfung nicht möglich.");
  else if (dlc === null || !Number.isInteger(dlc) || dlc < 0) add("PAYLOAD_MISSING", "OPEN", "Nachrichtengröße in Byte fehlt oder ist ungültig.");

  let occupiedBits: number[] | null = null;
  if (validBits && validStart && ["little_endian", "big_endian"].includes(byteOrder)) {
    occupiedBits = [];
    let position = start;
    // DBC: Intel starts at the LSB; Motorola starts at the MSB and crosses bytes.
    for (let index = 0; index < bits; index++) {
      occupiedBits.push(position);
      position = byteOrder === "little_endian" ? position + 1 : position % 8 === 0 ? position + 15 : position - 1;
    }
    if (dlc !== null && occupiedBits.some((bit) => bit >= dlc * 8)) add("PAYLOAD_OVERFLOW", "ERROR", `Signal liegt außerhalb der ${dlc} Byte großen Nachricht.`);
  }

  let requiredBits: number | null = null;
  const isFloat = /^(float|double|float32|float64)$/.test(dataType);
  const isSigned = /^(signed|int|int8|int16|int32|int64|sint8|sint16|sint32|sint64)$/.test(dataType);
  const isUnsigned = /^(unsigned|uint|uint8|uint16|uint32|uint64|boolean|bool)$/.test(dataType);
  if (factor === 0) add("SCALE_ZERO", "ERROR", "Skalierungsfaktor darf nicht 0 sein.");
  if (factor === null || offset === null) add("SCALING_MISSING", "OPEN", "Faktor oder Offset fehlt; keine belastbare Bitoptimierung.");
  if (min === null || max === null) add("RANGE_MISSING", "OPEN", "Wertebereich fehlt; notwendige Bitbreite bleibt offen.");
  else if (min > max) add("RANGE_REVERSED", "ERROR", "Minimum ist größer als Maximum.");
  else if (min === max) add("RANGE_CONSTANT", "OPEN", "Konstanter oder unspezifizierter Wertebereich; Bitoptimierung erfordert eine fachliche Vorgabe.");
  if (isFloat) {
    if (validBits && (dataType === "double" || dataType === "float64" ? bits !== 64 : dataType === "float32" ? bits !== 32 : ![32, 64].includes(bits))) add("FLOAT_WIDTH", "ERROR", "Gleitkommaformat und Bitbreite passen nicht zusammen.");
    add("FLOAT_PRECISION", "OPEN", "Gleitkomma-Präzision muss vor einer Verkleinerung nachgewiesen werden; ein kleiner Wertebereich genügt nicht.");
  } else if (!isSigned && !isUnsigned) {
    add("DATA_TYPE", "OPEN", dataType === "enum" ? "Vollständige Enum- und Fehlercodetabelle für die Bitprüfung erforderlich." : "Datentyp für die Bitprüfung fehlt oder wird nicht unterstützt.");
  } else if (min !== null && max !== null && min < max && factor !== null && factor !== 0 && offset !== null) {
    const values = [min, max];
    const data = record(signal.data);
    for (const key of ["default_value", "invalid_value"]) {
      if (data[key] != null) {
        const value = numeric(data[key]);
        if (value === null) add("SPECIAL_VALUE", "OPEN", `${key} ist nicht numerisch definiert.`);
        else {
          values.push(value);
          if (key === "default_value" && (value < min || value > max)) add("DEFAULT_RANGE", "ERROR", "Defaultwert liegt außerhalb des gültigen Wertebereichs.");
        }
      }
    }
    if (record(signal.configuration).reserved_values != null || data.reserved_values != null) add("RESERVED_VALUES", "OPEN", "Reservierte Codes müssen vor einer Verkleinerung separat bestätigt werden.");
    const raw = values.map((value) => (value - offset) / factor);
    if (raw.some((value) => !Number.isSafeInteger(Math.round(value)))) add("NUMERIC_PRECISION", "OPEN", "Rohwerte überschreiten die exakt prüfbare Ganzzahlpräzision.");
    else if (raw.some((value) => Math.abs(value - Math.round(value)) > Math.max(1e-8, Math.abs(value) * Number.EPSILON * 4))) add("QUANTIZATION", "ERROR", "Grenz- oder Sonderwerte sind bei dieser Skalierung nicht exakt darstellbar.");
    else {
      const rawMin = Math.min(...raw.map(Math.round)), rawMax = Math.max(...raw.map(Math.round));
      if (!isSigned && rawMin < 0) add("UNSIGNED_NEGATIVE", "ERROR", "Unsigned-Signal benötigt negative Rohwerte; Datentyp oder Offset korrigieren.");
      else {
        for (let width = 1; width <= 64; width++) {
          if (isSigned ? rawMin >= -(2 ** (width - 1)) && rawMax < 2 ** (width - 1) : rawMax < 2 ** width) { requiredBits = width; break; }
        }
        if (validBits && requiredBits !== null && requiredBits > bits) add("TOO_NARROW", "ERROR", `${bits} Bit reichen nicht; mindestens ${requiredBits} Bit sind erforderlich.`);
        if (/^(bool|boolean)$/.test(dataType) && (rawMin < 0 || rawMax > 1)) add("BOOLEAN_RANGE", "ERROR", "Boolean darf nur die Rohwerte 0 und 1 verwenden.");
      }
    }
    const resolution = numeric(data.resolution);
    if (resolution !== null && (resolution <= 0 || Math.abs(factor) > resolution * (1 + Number.EPSILON * 4))) add("RESOLUTION", "ERROR", "Skalierung erfüllt die angeforderte Auflösung nicht.");
  }
  if (validBits && requiredBits !== null && requiredBits < bits && !checks.some((check) => check.severity !== "WARNING")) {
    add("OVERSIZED", "WARNING", `Rechnerisch ${requiredBits} statt ${bits} Bit ausreichend, bei unverändertem Wertebereich, Faktor und Offset. Protokollbindung, Reserven und Freigabe prüfen; nicht automatisch ändern.`);
  }
  return { id: signal.id, name: text(signal.display_name) || text(signal.name) || signal.id,
    messageId: text(signal.message_id), messageName: text(message?.name) || text(signal.message_id), bits, requiredBits, start,
    dataType, byteOrder, min, max, factor, offset, unit: text(signal.unit), occupiedBits, checks, status: checkStatus(checks) };
}

export function inspectMessageSignals(signals: InspectionObject[], message?: InspectionObject): SignalInspection[] {
  const inspected = signals.map((signal) => inspectSignal(signal, message));
  const occupants = new Map<number, number[]>();
  inspected.forEach((signal, index) => signal.occupiedBits?.forEach((bit) => occupants.set(bit, [...(occupants.get(bit) ?? []), index])));
  const overlaps = new Map<number, Set<number>>();
  for (const indexes of occupants.values()) if (indexes.length > 1) {
    for (const index of indexes) for (const other of indexes) if (other !== index) {
      if (!overlaps.has(index)) overlaps.set(index, new Set());
      overlaps.get(index)!.add(other);
    }
  }
  for (const [index, others] of overlaps) {
    const multiplexed = [index, ...others].some((item) => hasMultiplexing(signals[item]));
    inspected[index].checks.push({ code: "OVERLAP", severity: multiplexed ? "OPEN" : "ERROR",
      text: `${multiplexed ? "Multiplex-Belegung separat prüfen" : "Bitüberlappung"}: ${[...others].map((other) => inspected[other].name).join(", ")}.` });
    inspected[index].status = checkStatus(inspected[index].checks);
  }
  return inspected;
}

export function buildNetworkInspection(networkId: string, data: InspectionSources) {
  const hardware = new Map(data.hardware.map((item) => [item.id, item]));
  const interfaces = new Map(data.interfaces.map((item) => [item.id, item]));
  const functions = new Map(data.functions.map((item) => [item.id, item]));
  const nodes = objects(data.topology.nodes), edges = objects(data.topology.edges);
  const nodeById = new Map(nodes.map((item) => [item.id, item]));
  const nodeByHardware = new Map(nodes.map((item) => [text(item.engineeringId) || item.id, item]));
  const hardwareId = (value: unknown) => text(nodeById.get(text(value))?.engineeringId) || text(value);
  const routes = data.routes.filter((route) => text(record(route.source).network_id) === networkId || objects(route.destinations).some((item) => text(item.network_id) === networkId));
  const roles = new Map<string, Set<string>>(), interfaceIds = new Map<string, Set<string>>(), seeds = new Set<string>();
  const addParticipant = (id: string, role: string, interfaceId = "") => {
    if (!id) return;
    if (!roles.has(id)) roles.set(id, new Set());
    roles.get(id)!.add(role);
    if (!interfaceIds.has(id)) interfaceIds.set(id, new Set());
    if (interfaceId) interfaceIds.get(id)!.add(interfaceId);
  };
  const addEndpoint = (endpoint: Record<string, unknown>, role: string) => {
    if (endpoint.network_id !== networkId) return;
    const iface = interfaces.get(text(endpoint.interface_id));
    const id = hardwareId(endpoint.node_id) || text(iface?.hardware_node_id) || text(functions.get(text(iface?.function_id))?.hardware_node_id);
    addParticipant(id, role, text(endpoint.interface_id));
    const node = nodeByHardware.get(id);
    const port = objects(node?.ports).find((port) => port.id === endpoint.port_id || port.engineeringId === endpoint.interface_id);
    if (node && port) seeds.add(`${node.id}:${port.id}`);
  };
  for (const route of routes) {
    addEndpoint(record(route.source), "Sender");
    objects(route.destinations).forEach((endpoint) => addEndpoint(endpoint, "Empfänger"));
  }
  // Follow connected ports, never bridge separate gateway interfaces into one bus.
  let changed = true;
  while (changed) {
    changed = false;
    for (const edge of edges) {
      const a = `${edge.source}:${edge.sourcePort}`, b = `${edge.target}:${edge.targetPort}`;
      if (!seeds.has(a) && !seeds.has(b)) continue;
      for (const [nodeId, portId, key] of [[edge.source, edge.sourcePort, a], [edge.target, edge.targetPort, b]]) {
        if (!seeds.has(text(key))) { seeds.add(text(key)); changed = true; }
        const node = nodeById.get(text(nodeId));
        const port = objects(node?.ports).find((item) => item.id === portId);
        addParticipant(hardwareId(nodeId), "Physisch verbunden", text(port?.engineeringId));
      }
    }
  }
  const participants = [...roles].map(([id, participantRoles]) => {
    const item = hardware.get(id), node = nodeByHardware.get(id);
    const identity = record(item?.identity);
    const ownerId = item?.device_type === "ECU" ? id : hardwareId(identity.system_owner_id || node?.systemOwnerId);
    const owner = hardware.get(ownerId);
    const hasExplicitOwner = !!text(identity.system_owner_id) || ownerId === id;
    return { id, name: text(item?.name) || text(node?.name) || id, type: text(item?.device_type) || text(node?.kind) || "Unbekannt",
      roles: [...participantRoles], interfaces: [...(interfaceIds.get(id) ?? [])].map((id) => ({ id, name: text(interfaces.get(id)?.name) || id })),
      system: owner ? { id: owner.id, name: text(owner.name) || owner.id, basis: hasExplicitOwner ? "explicit" : text(node?.systemOwnerSource) || "explicit" } : null };
  });
  const notices: string[] = [];
  const messageIds = new Set<string>(), signalIds = new Set<string>();
  const signalById = new Map(data.signals.map((item) => [item.id, item]));
  for (const route of routes) {
    const payload = record(route.payload);
    for (const id of [text(payload.message_id), ...strings(payload.message_ids)]) if (id) messageIds.add(id);
    for (const id of strings(payload.signal_ids)) {
      signalIds.add(id);
      const signal = signalById.get(id);
      if (signal?.message_id) messageIds.add(text(signal.message_id));
      if (!signal) notices.push(`Signalreferenz ${id} ist nicht auflösbar.`);
    }
  }
  for (const signal of data.signals) if (messageIds.has(text(signal.message_id))) signalIds.add(signal.id);
  const selectedSignals = data.signals.filter((signal) => signalIds.has(signal.id));
  const checks: SignalInspection[] = [];
  const messages = [...messageIds].map((id) => {
    const message = data.messages.find((item) => item.id === id);
    if (!message) notices.push(`Nachrichtenreferenz ${id} ist nicht auflösbar.`);
    const signals = selectedSignals.filter((item) => item.message_id === id);
    const inspected = inspectMessageSignals(signals, message);
    checks.push(...inspected);
    const positions = new Set(inspected.flatMap((item) => item.occupiedBits ?? []));
    const layoutKnown = signals.length > 0 && inspected.every((item) => item.occupiedBits !== null && !item.checks.some((check) => ["OVERLAP", "PAYLOAD_OVERFLOW", "PAYLOAD_MISSING"].includes(check.code)));
    const minimumBytes = layoutKnown ? Math.ceil((Math.max(...positions) + 1) / 8) : null;
    const iface = interfaces.get(text(message?.interface_id));
    const senderId = text(iface?.hardware_node_id) || text(functions.get(text(iface?.function_id))?.hardware_node_id);
    return { id, name: text(message?.name) || id, bytes: numeric(message?.dlc), signalCount: signals.length,
      occupiedBits: layoutKnown ? positions.size : null, minimumBytes,
      origin: text(hardware.get(senderId)?.name) || senderId || "Nicht zugeordnet" };
  });
  for (const signal of selectedSignals) if (!messageIds.has(text(signal.message_id))) checks.push(inspectSignal(signal));
  if (!routes.length) notices.push("Keine aktuellen Routen für dieses Netz; Analyse und Modellzuordnung prüfen.");
  if (!signalIds.size) notices.push("Keine Signale in den zugeordneten Nachrichten oder Routen gefunden.");
  return { networkId, versions: data.versions, participants, messages, signals: checks, notices,
    counts: { participants: participants.length, senders: participants.filter((item) => item.roles.includes("Sender")).length,
      systems: new Set(participants.flatMap((item) => item.system ? [item.system.id] : [])).size,
      messages: messageIds.size, signals: signalIds.size, missingSignals: signalIds.size - selectedSignals.length,
      errors: checks.filter((item) => item.status === "ERROR").length, warnings: checks.filter((item) => item.status === "WARNING").length,
      open: checks.filter((item) => item.status === "OPEN").length, passed: checks.filter((item) => item.status === "PASS").length } };
}
export type NetworkInspection = ReturnType<typeof buildNetworkInspection>;
