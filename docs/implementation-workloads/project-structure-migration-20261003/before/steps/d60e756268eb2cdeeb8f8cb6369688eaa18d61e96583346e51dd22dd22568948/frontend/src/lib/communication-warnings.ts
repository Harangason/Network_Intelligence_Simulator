import type { EngineeringObject, EngMessage, HardwareNetworkInterface, RoutingEntry } from './types';
import type { NetworkTopology } from './topology';
import { engineeringParent, engineeringOwnership } from './engineering-ownership.ts';

export type CommunicationWarning = {
  key: string;
  code: string;
  reason: string;
  fields: string[];
  routeId?: string;
  routeCode?: string;
  messageId?: string;
  messageName?: string;
};
export type CommunicationWarnings = Map<string, CommunicationWarning[]>;

/** Assess current references; a saved VALID/APPROVED flag is not connection evidence.
 * Propagate upwards and through the affected payload only, never to sibling messages.
 */
export function communicationWarnings(objects: EngineeringObject[], routes: RoutingEntry[], networks: { id: string; name?: string }[], topology: Partial<NetworkTopology>): CommunicationWarnings {
  const byId = new Map(objects.map(item => [item.id, item]));
  const ports = objects.filter((item): item is HardwareNetworkInterface => item.object_type === 'HardwareNetworkInterface');
  const messages = objects.filter((item): item is EngMessage => item.object_type === 'Message');
  const networkIds = new Set(networks.map(item => item.id));
  const connected = new Set((topology.edges ?? []).flatMap(edge => [edge.sourcePort, edge.targetPort]));
  const activePorts = new Set<string>();
  const aliases = new Map(ports.map(port => [port.id, port]));
  const signalsByMessage = new Map<string, string[]>();
  const collected = new Map<string, Map<string, CommunicationWarning>>();
  for (const port of ports) {
    if (port.physical_port_ref) aliases.set(port.physical_port_ref, port);
  }
  for (const node of topology.nodes ?? []) for (const port of node.ports ?? []) {
    const canonical = byId.get(port.hardwareInterfaceId ?? '');
    if (!canonical || canonical.object_type !== 'HardwareNetworkInterface' || !('network_ref' in canonical)) continue;
    aliases.set(port.id, canonical);
    if (connected.has(port.id) && canonical.hardware_node_id === node.engineeringId && canonical.network_ref === port.physicalNetworkId) activePorts.add(canonical.id);
  }
  for (const item of objects) if ('message_id' in item && item.object_type === 'Signal' && item.message_id) {
    signalsByMessage.set(item.message_id, [...(signalsByMessage.get(item.message_id) ?? []), item.id]);
  }
  function add(id: string | undefined | null, issue: CommunicationWarning) {
    const visited = new Set<string>();
    let current = id ? byId.get(id) : undefined;
    while (current && !visited.has(current.id)) {
      visited.add(current.id);
      const issues = collected.get(current.id) ?? new Map<string, CommunicationWarning>();
      issues.set(issue.key, issue);
      collected.set(current.id, issues);
      const parent = engineeringParent(current);
      current = parent?.id ? byId.get(parent.id) : undefined;
      if (current && current.object_type !== parent?.type) break;
    }
  }
  function portProblem(port: HardwareNetworkInterface | undefined): { code: string; reason: string } | null {
    if (!port) return { code: 'PORT_MISSING', reason: 'Der physische Anschluss fehlt.' };
    if (!port.network_ref) return { code: 'BUS_UNASSIGNED', reason: `Anschluss „${port.name}“ (Kanal ${port.channel_index ?? 'offen'}) ist keinem Bus zugeordnet.` };
    if (!networkIds.has(port.network_ref)) return { code: 'BUS_MISSING', reason: `Der Bus des Anschlusses „${port.name}“ existiert nicht mehr.` };
    if (!activePorts.has(port.id)) return { code: 'PORT_DISCONNECTED', reason: `Anschluss „${port.name}“ ist im aktuellen Netzwerk nicht verbunden.` };
    return null;
  }
  for (const port of ports) {
    const problem = portProblem(port);
    if (problem) add(port.id, { ...problem, key: `port:${port.id}`, fields: ['Anschluss', 'Buszuordnung'] });
  }
  for (const message of messages) {
    const extra = message.configuration?.physical_transmit_bindings;
    const bindings = [{ hardware_interface_id: message.hardware_interface_id, network_id: undefined as string | undefined },
      ...(Array.isArray(extra) ? extra : [])];
    for (const [index, binding] of bindings.entries()) {
      const port = aliases.get(binding.hardware_interface_id ?? '');
      const owner = engineeringOwnership(message, byId).hardware;
      const problem = portProblem(port)
        ?? (port && owner && owner.id !== port.hardware_node_id
          ? { code: 'MESSAGE_PORT_OWNER_MISMATCH', reason: 'Der Sendeanschluss gehört zu einem anderen Gerät als die Nachricht.' } : null)
        ?? (binding.network_id && port?.network_ref !== binding.network_id
          ? { code: 'MESSAGE_BUS_MISMATCH', reason: 'Der zusätzliche Sendepfad verweist auf einen anderen Bus als der Anschluss.' } : null);
      if (!problem) continue;
      const issue = { ...problem, key: `message:${message.id}:${index}`, fields: ['Sendeanschluss', 'Buszuordnung'], messageId: message.id, messageName: message.name };
      add(message.id, issue);
      for (const id of signalsByMessage.get(message.id) ?? []) add(id, issue);
    }
  }
  for (const route of routes) {
    if (['REJECTED', 'SUPERSEDED'].includes(route.status)) continue;
    const payload = route.payload;
    const messageIds = new Set([payload.message_id, ...(payload.message_ids ?? [])].filter((id): id is string => Boolean(id)));
    for (const id of payload.signal_ids ?? []) {
      const signal = byId.get(id);
      if (signal && 'message_id' in signal && signal.message_id) messageIds.add(signal.message_id);
    }
    function affect(issue: CommunicationWarning) {
      for (const endpoint of [route.source, ...route.destinations]) {
        add(endpoint.interface_id, issue);
        add(endpoint.node_id, issue);
        add(aliases.get(endpoint.port_id ?? '')?.id, issue);
      }
      for (const id of messageIds) add(id, issue);
      const affectedSignals = payload.signal_ids?.length ? payload.signal_ids : [...messageIds].flatMap(id => signalsByMessage.get(id) ?? []);
      for (const id of affectedSignals) add(id, issue);
    }
    for (const [index, endpoint] of [route.source, ...route.destinations].entries()) {
      const port = aliases.get(endpoint.port_id ?? endpoint.physical_port_ref ?? '');
      const problem = portProblem(port)
        ?? (port?.hardware_node_id !== endpoint.node_id ? { code: 'ROUTE_PORT_OWNER_MISMATCH', reason: 'Der Routenanschluss gehört zu einem anderen Gerät.' } : null)
        ?? (port?.network_ref !== endpoint.network_id ? { code: 'ROUTE_BUS_MISMATCH', reason: 'Die Route verweist auf einen anderen Bus als ihr Anschluss.' } : null);
      if (problem) affect({ ...problem, key: `route:${route.id}:${index}`, routeId: route.id, routeCode: route.route_code,
        fields: [index === 0 ? 'Quellanschluss' : 'Zielanschluss', 'Buszuordnung', 'Routenprüfung'],
        reason: `${index === 0 ? 'Quelle' : 'Ziel'}: ${problem.reason}${route.approval_state === 'APPROVED' ? ' Die gespeicherte Freigabe passt nicht mehr zu diesem Anschluss.' : ''}` });
    }
    if (route.status === 'OUTDATED' || route.validation?.valid === false) {
      affect({ key: `route:${route.id}:validation`, code: 'ROUTE_REVIEW_REQUIRED', routeId: route.id, routeCode: route.route_code,
        reason: route.validation?.outdated_reason || route.validation?.errors?.map(issue => issue.message).join(' · ') || 'Die Route muss anhand des aktuellen Modells erneut geprüft werden.',
        fields: ['Routenprüfung', 'Timing', 'Kapazitätsbewertung'] });
    }
  }
  return new Map([...collected].map(([id, issues]) => [id, [...issues.values()]]));
}

export function communicationWarningText(issues: CommunicationWarning[]): string {
  return issues.length ? `${issues.length} Warnungen · ${issues.map(issue => [issue.routeCode, issue.messageName, issue.reason, ...issue.fields].filter(Boolean).join(' · ')).join(' / ')}` : '—';
}
