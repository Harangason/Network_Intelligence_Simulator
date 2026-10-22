

type ReferenceWire = {
  length_bits: number; data_type: ExtractedEngineeringChain['data_type']; unit: string; factor: number;
  offset_value?: number; min_value?: number | null; max_value?: number | null;
  byte_order?: ExtractedEngineeringChain['byte_order']; semantic: Record<string, unknown>; data: Record<string, unknown>;
};
type ReferenceParticipant = {
  id: string; name: string; kind: 'CONTROLLER' | 'GATEWAY' | 'SENSOR' | 'ACTUATOR' | 'PHYSICAL_CONTEXT';
  quantity: number; source_fact_ids: string[]; owner_device_id?: string | null; purpose?: string | null;
  rationale: string; context_kind?: string | null; contained_device_ids?: string[];
};
type ReferencePhysicalPort = {
  id: string; device_id: string; technology: string; network_scope: string;
  role: 'LOCAL' | 'BACKBONE'; parameters: Record<string, unknown>; rationale: string;
};
type ReferenceRelease = {
  id: string; producer_device_id: string; consumer_device_ids: string[];
  source_port_id: string; consumer_port_ids: string[]; scope: 'LOCAL_IO' | 'DEVICE_IO' | 'FUNCTION_OUTPUT';
  role?: 'MEASUREMENT' | 'COMMAND' | 'FEEDBACK' | 'STATUS' | 'FUNCTION_OUTPUT' | null;
  producer_fact_id?: string | null; consumer_fact_ids?: string[]; signal_name: string; encoding: ReferenceWire;
  transmission_mode: 'CYCLIC' | 'EVENT' | 'ON_REQUEST' | 'MIXED'; cycle_ms?: number | null;
  min_interval_ms?: number | null; trigger?: string | null; trigger_description?: string | null;
  release_times_ms?: number[] | null; request_source?: string | null; request_communication_id?: string | null;
  response_processing_ms?: number | null; request_times_ms?: number[] | null; rationale: string;
};
type ReferencePlan = {
  devices: ReferenceParticipant[]; ports: ReferencePhysicalPort[]; communication: ReferenceRelease[];
  functions: Array<{ source_fact_id: string; realization: 'ATOMIC' | 'COMPOSITE'; executor_device_ids: string[]; realized_by_fact_ids: string[] }>;
  measurements: Array<{ device_id: string; measurement_id: string }>;
  commands: Array<{ device_id: string; definition: ReferenceWire }>;
  functional_dependencies?: Array<Record<string, unknown>>;
  unresolved: Array<{ code: string; target_ref: string; message: string }>;
};
export type AcceptedDocumentReferenceDesign = {
  schema_version: 1; design_id: string; revision: number; request_sha256: string; source_sha256: string;
  status: 'ACCEPTED'; proposal: ReferencePlan; fact_id_map: Record<string, string>;
  decision_evidence: Array<Record<string, unknown>>; protected_fields: Record<string, Record<string, unknown>>;
};

/** This selects review data only. The server checks its stored design/revision. */
export function readDocumentReferenceDesign(text: string): AcceptedDocumentReferenceDesign | undefined {
  const marker = [...text.matchAll(/^- Dokument-Referenzentwurf:\s*([^\r\n]+)$/gm)].at(-1);
  if (!marker) return;
  const value = JSON.parse(marker[1]) as AcceptedDocumentReferenceDesign;
  if (!value || value.schema_version !== 1 || value.status !== 'ACCEPTED'
      || typeof value.design_id !== 'string' || !value.design_id.trim()
      || !Number.isSafeInteger(value.revision) || value.revision < 1
      || !/^[a-f0-9]{64}$/.test(value.request_sha256) || !/^[a-f0-9]{64}$/.test(value.source_sha256)
      || !value.proposal || !Array.isArray(value.proposal.devices) || !Array.isArray(value.proposal.ports)
      || !Array.isArray(value.proposal.communication) || !Array.isArray(value.proposal.functions)
      || !Array.isArray(value.proposal.measurements) || !Array.isArray(value.proposal.commands)
      || !Array.isArray(value.proposal.unresolved) || !value.fact_id_map) {
    throw new Error('Der Referenzentwurf benötigt eine aktuelle, ausdrücklich übernommene Revision.');
  }
  const source = readReviewedDocumentEquipment(text);
  if (!source?.facts || source.source_sha256 !== value.source_sha256)
    throw new Error('Der Referenzentwurf gehört nicht zur unveränderten vollständigen Dokumentquelle.');
  const original = new Set(source.facts.map(fact => documentFactIdentity(fact)));
  const identities = Object.values(value.fact_id_map);
  if (identities.length !== original.size || new Set(identities).size !== identities.length
      || identities.some(identity => !original.has(identity))
      || Object.keys(value.fact_id_map).some(id => !/^F[a-f0-9]{12}$/.test(id)))
    throw new Error('Die ursprünglichen Quellenbefunde des Referenzentwurfs sind unvollständig oder verändert.');
  return value;
}

export function isReferenceDesignChain(chain: ExtractedEngineeringChain) {
  return typeof chain.configuration?.reference_design_id === 'string';
}

/** Compile an already reviewed NIS plan through the existing chain contract. */
function extractReferenceDesignSpecification(
  text: string, selection: AcceptedDocumentReferenceDesign,
  overrides: Partial<EngineeringHardwareCounts>, domainOverride?: string,
): ExtractedEngineeringSpecification {
  const originalText = text.replace(/^- Dokument-Referenzentwurf:[^\r\n]*\r?\n?/gm, '');
  const base = extractEngineeringSpecification(originalText, overrides, domainOverride);
  const plan = structuredClone(selection.proposal);
  const unique = <T extends { id: string }>(items: T[], label: string) => {
    const values = new Map(items.map(item => [item.id, item]));
    if (values.size !== items.length) throw new Error(`${label}: doppelte Referenzidentität.`);
    return values;
  };
  const devices = unique(plan.devices, 'Teilnehmer');
  const ports = unique(plan.ports, 'Anschlüsse');
  unique(plan.communication, 'Kommunikation');
  const functions = new Map(plan.functions.map(item => [item.source_fact_id, item]));
  const source = readReviewedDocumentEquipment(text)!;
  const sourceFacts = new Map(source.facts!.map(fact => [documentFactIdentity(fact), fact]));
  const fact = (id: string) => {
    const found = sourceFacts.get(selection.fact_id_map[id]);
    if (!found) throw new Error(`Unbekannter ursprünglicher Quellenbefund ${id}.`);
    return found;
  };
  const names = new Set<string>();
  for (const device of devices.values()) {
    const identity = normalizeHardwareName(device.name).toLocaleLowerCase('de');
    if (!device.name.trim() || names.has(identity)) throw new Error('Referenzteilnehmer benötigen eindeutige technische Namen.');
    names.add(identity);
    if (device.kind !== 'PHYSICAL_CONTEXT' && device.quantity !== 1)
      throw new Error(`${device.name}: Der NIS-Referenzplan muss elektronisch adressierte Teilnehmer einzeln mit eindeutigen IDs ausweisen. Eine Gruppenmenge bestätigt keine Port- oder Ausführerzuordnung.`);
    device.source_fact_ids.forEach(fact);
  }
  const electronic = (id: string) => {
    const device = devices.get(id);
    if (!device || device.kind === 'PHYSICAL_CONTEXT') throw new Error('Ein physischer Anschluss benötigt einen elektronischen Referenzteilnehmer.');
    return device;
  };
  const wireType = (device: ReferenceParticipant) => {
    if (device.kind === 'GATEWAY') return 'Gateway';
    if (device.kind === 'SENSOR') return 'SensorController';
    if (device.kind === 'ACTUATOR') return 'ActuatorController';
    const previous = base.chains.find(chain => normalizeHardwareName(chain.hardware_name).toLocaleLowerCase('de')
      === normalizeHardwareName(device.name).toLocaleLowerCase('de') && isEngineeringControllerDevice(chain.device_type));
    return previous?.device_type ?? controllerDeviceTypeForModel(base.modelType || base.domain);
  };
  const projection = new Map(technologyProjection.technologies.map(item => [item.id, item]));
  for (const port of ports.values()) {
    electronic(port.device_id);
    if (!projection.has(port.technology)) throw new Error(`Nicht registrierte Referenztechnologie ${port.technology}.`);
  }
  const measurements = new Map(plan.measurements.map(item => [item.device_id, item.measurement_id]));
  const commands = new Map(plan.commands.map(item => [item.device_id, item.definition]));
  const inherited = (field: string, device: ReferenceParticipant) => {
    const identity = normalizeHardwareName(device.name).toLocaleLowerCase('de');
    return Object.entries(selection.protected_fields[field] ?? {}).find(([name]) =>
      normalizeHardwareName(name).toLocaleLowerCase('de') === identity)?.[1];
  };
  const contextFor = (device: ReferenceParticipant) => device.source_fact_ids.map(id => fact(id).source_context ?? []);
  const configuration = (device: ReferenceParticipant, port?: ReferencePhysicalPort) => {
    const inheritedOwner = inherited('owners', device);
    const owner = device.owner_device_id ? electronic(device.owner_device_id)
      : typeof inheritedOwner === 'string' ? [...devices.values()].find(item =>
        normalizeHardwareName(item.name).toLocaleLowerCase('de') === normalizeHardwareName(inheritedOwner).toLocaleLowerCase('de')) : undefined;
    const measurement = measurements.get(device.id) ?? inherited('measurements', device);
    const command = commands.get(device.id) ?? inherited('commands', device);
    return {
      reference_design_id: selection.design_id, reference_design_revision: selection.revision,
      reference_request_sha256: selection.request_sha256, reference_source_sha256: selection.source_sha256,
      reference_device_id: device.id, reference_source_fact_ids: [...device.source_fact_ids],
      reference_source_contexts: contextFor(device), reference_device: structuredClone(device),
      reference_port_id: port?.id ?? null, reference_port: port ? structuredClone(port) : null,
      design_evidence: 'REFERENCE_ASSUMPTION', processing_evidence: 'NONE', timing_evidence: 'NONE',
      ...(owner ? { functional_owner: owner.name, functional_owner_source: device.owner_device_id ? 'reference_assumption' : 'explicit_user_statement' } : {}),
      ...(measurement ? { sensor_measurement: measurement, measurement_source: measurements.has(device.id) ? 'reference_assumption' : 'explicit_user_statement' } : {}),
      ...(command && typeof command === 'object' ? { actuator_command_template: commands.has(device.id)
        ? { ...structuredClone(command), source: 'wizard-reference-design-v1', design_evidence: 'REFERENCE_ASSUMPTION' }
        : structuredClone(command) } : {}),
    };
  };
  const receiveOnly = (device: ReferenceParticipant, port?: ReferencePhysicalPort): ExtractedEngineeringChain => ({
    hardware_name: device.name, hardware_description: device.purpose ?? device.rationale, device_type: wireType(device),
    function_name: '', function_description: '', interface_name: port ? `${device.name}_${port.id}` : '',
    interface_type: port?.technology ?? 'Other', transport_network_ref: port?.network_scope,
    message_name: '', message_id_hex: '0x0', direction: 'tx', cycle_ms: 0, dlc: 0,
    signal_name: '', signal_display_name: '', start_bit: 0, length_bits: 0, byte_order: 'little_endian',
    data_type: 'unsigned', factor: 1, offset_value: 0, domain: base.domain,
    configuration: { ...configuration(device, port), reference_receive_only: true,
      reference_no_port: !port, reference_communication_id: null },
    quality: { validation_status: 'REFERENCE_REVIEW_REQUIRED', hardware_evidence: false },
  });
  const chains: ExtractedEngineeringChain[] = [];
  const transmittedPorts = new Set<string>();
  const releaseContract = (row: ReferenceRelease): Record<string, unknown> => {
    const result: Record<string, unknown> = { mode: row.transmission_mode };
    const fields = { cycle_ms: 'period_ms', min_interval_ms: 'minimum_interval_ms', trigger: 'trigger',
      trigger_description: 'trigger_description', release_times_ms: 'release_times_ms', request_source: 'request_source',
      response_processing_ms: 'response_processing_ms', request_times_ms: 'request_times_ms' } as const;
    for (const [from, to] of Object.entries(fields)) {
      const value = row[from as keyof typeof fields];
      if (value != null) result[to] = structuredClone(value);
    }
    if (row.request_communication_id) result.reference_request_communication_id = row.request_communication_id;
    return result;
  };
  for (const [index, row] of plan.communication.entries()) {
    const producer = electronic(row.producer_device_id);
    const port = ports.get(row.source_port_id);
    if (!port || port.device_id !== producer.id) throw new Error(`${row.id}: eindeutiger Senderanschluss fehlt.`);
    if (row.consumer_port_ids.length !== row.consumer_device_ids.length) throw new Error(`${row.id}: Empfängeranschlüsse sind unvollständig.`);
    const consumers = row.consumer_device_ids.map((id, i) => {
      const device = electronic(id), endpoint = ports.get(row.consumer_port_ids[i]);
      if (!endpoint || endpoint.device_id !== id || id === producer.id) throw new Error(`${row.id}: tatsächlicher Empfängeranschluss fehlt oder verweist auf Selbsttransport.`);
      return device;
    });
    if (!consumers.length) throw new Error(`${row.id}: bewusste Empfänger fehlen.`);
    const sourceFunction = row.producer_fact_id ? functions.get(row.producer_fact_id) : undefined;
    if (row.producer_fact_id && (!sourceFunction || sourceFunction.realization !== 'ATOMIC'
        || !sourceFunction.executor_device_ids.includes(producer.id)))
      throw new Error(`${row.id}: Senderfunktion muss eine konkrete atomare Realisierung auf dem Sender sein.`);
    const wire = row.encoding;
    const rawBytes = Math.ceil(wire.length_bits / 8);
    const technology = projection.get(port.technology)!;
    if (technology.max_payload_bytes != null && rawBytes > technology.max_payload_bytes)
      throw new Error(`${row.id}: Nutzlast überschreitet das registrierte Technologieprofil.`);
    // Existing CAN-FD padding classes are shared with ordinary frame packing.
    const payload = port.technology === 'can_fd' ? validPayloadBytes('canfd', rawBytes) : rawBytes;
    if (!payload || payload < rawBytes) throw new Error(`${row.id}: Nutzlast benötigt eine explizite Segmentierungsplanung.`);
    const functionName = row.producer_fact_id ? `${producer.name}_${fact(row.producer_fact_id).name}` : `${producer.name}_${row.signal_name}`;
    const role = row.role ?? (producer.kind === 'SENSOR' ? 'MEASUREMENT' : producer.kind === 'ACTUATOR' ? 'FEEDBACK'
      : consumers.every(device => device.kind === 'ACTUATOR') ? 'COMMAND' : 'FUNCTION_OUTPUT');
    const numeric = wire.semantic.semantic_type === 'NUMERIC';
    chains.push({
      ...receiveOnly(producer, port),
      function_name: conciseGeneratedName('Function', functionName), function_description: row.rationale,
      message_name: `${producer.name}_${row.id}`, message_id_hex: `0x${(0x180 + index).toString(16).toUpperCase()}`,
      signal_name: conciseGeneratedName('Signal', `${producer.name}_${row.id}_${row.signal_name}`), signal_display_name: row.signal_name,
      cycle_ms: row.cycle_ms ?? row.min_interval_ms ?? 0, dlc: payload, length_bits: wire.length_bits,
      byte_order: wire.byte_order ?? 'little_endian', data_type: wire.data_type, factor: wire.factor,
      offset_value: wire.offset_value ?? 0, unit: wire.unit,
      ...(wire.min_value != null ? { min_value: wire.min_value } : {}),
      ...(wire.max_value != null ? { max_value: wire.max_value } : {}),
      semantic: structuredClone(wire.semantic), data: structuredClone(wire.data),
      configuration: { ...configuration(producer, port), reference_receive_only: false,
        reference_communication_id: row.id, reference_function_fact_id: row.producer_fact_id ?? null,
        reference_communication: structuredClone(row), transmission: releaseContract(row),
        raw_datatype: wire.data_type, bit_length: wire.length_bits, signed: wire.data_type === 'signed',
        factor: wire.factor, offset: wire.offset_value ?? 0, endianness: wire.byte_order ?? 'little_endian', start_bit: 0,
        encoding_type: numeric ? 'linear' : wire.semantic.semantic_type === 'BYTE_ARRAY' ? 'raw' : 'coded',
        ...(wire.data.structured_payload ? { structured_payload: structuredClone(wire.data.structured_payload) } : {}),
        communication_contract: { scope: row.scope, role, design_evidence: 'REFERENCE_ASSUMPTION' },
      },
      communication: { producer: producer.name, consumers: consumers.map(device => device.name),
        transmission_mode: row.transmission_mode, ...(row.cycle_ms != null ? { cycle_time_ms: row.cycle_ms } : {}) },
      quality: { semantic_complete: true, value_domain_complete: true, encoding_complete: true,
        validation_status: 'REFERENCE_REVIEW_REQUIRED', hardware_evidence: false },
    });
    transmittedPorts.add(port.id);
  }
  for (const device of devices.values()) {
    if (device.kind === 'PHYSICAL_CONTEXT') continue;
    const physicalPorts = [...ports.values()].filter(port => port.device_id === device.id);
    if (!physicalPorts.length) chains.push(receiveOnly(device));
    else for (const port of physicalPorts) if (!transmittedPorts.has(port.id)) chains.push(receiveOnly(device, port));
  }
  const counts = { ecus: 0, gateways: 0, sensors: 0, actuators: 0, explicit: true };
  for (const device of devices.values()) {
    if (device.kind === 'CONTROLLER') counts.ecus++;
    else if (device.kind === 'GATEWAY') counts.gateways++;
    else if (device.kind === 'SENSOR') counts.sensors++;
    else if (device.kind === 'ACTUATOR') counts.actuators++;
  }
  const networks = new Map<string, Set<string>>();
  for (const port of ports.values()) networks.set(port.technology, new Set([...(networks.get(port.technology) ?? []), port.network_scope]));
  return { ...base, chains, interfaceType: plan.ports[0]?.technology ?? 'Other',
    communicationSystems: [...networks.keys()], communicationSystemCounts: Object.fromEntries([...networks].map(([id, values]) => [id, values.size])),
    targetCounts: counts, unresolvedInventoryGroups: plan.unresolved.map(item => item.message),
    reference_design: { ...structuredClone(selection), original_facts: structuredClone(source.facts),
      processing_evidence: 'NONE', timing_evidence: 'NONE' },
  };
}
