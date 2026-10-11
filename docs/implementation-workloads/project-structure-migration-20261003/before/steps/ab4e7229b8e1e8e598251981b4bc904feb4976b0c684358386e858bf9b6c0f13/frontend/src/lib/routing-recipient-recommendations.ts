import type { EngInterface, EngSignal, HardwareNode, RoutingEntry } from './types';
import type { ScopedMessage } from './routing-payload-scope';

export type RecipientRecommendation = { nodeId: string; reason: string; confidence: number | null };
export function recipientRecommendations(sourceId: string, messages: ScopedMessage[], routes: RoutingEntry[], interfaces: EngInterface[], signals: EngSignal[] = []) {
  const result = new Map<string, RecipientRecommendation>();
  const byRef = new Map<string, Set<string>>();
  for (const item of interfaces) if (item.hardware_node_id) {
    for (const ref of [item.id, item.function_id, item.hardware_node_id]) if (ref) {
      const nodes = byRef.get(ref) ?? new Set<string>(); nodes.add(item.hardware_node_id); byRef.set(ref, nodes);
    }
  }
  const messageIds = new Set(messages.map(message => message.id));
  const signalParents = new Map(signals.map(signal => [signal.id, signal.message_id]));
  for (const message of messages) for (const ref of message.routingScope?.consumer_refs ?? []) {
    const resolved = byRef.get(ref) ?? new Set([ref]);
    if (resolved.size > 1) continue;
    for (const nodeId of resolved) if (nodeId !== sourceId) {
      result.set(nodeId, { nodeId, confidence: null, reason: `Als Empfänger von „${message.name}“ im Kommunikationsvertrag hinterlegt` });
    }
  }
  for (const route of routes) {
    if (route.source.node_id !== sourceId || ['DEPRECATED', 'SUPERSEDED', 'REJECTED', 'OUTDATED', 'CONFLICT'].includes(route.status) || route.approval_state === 'REJECTED' || !route.validation?.valid) continue;
    const payload = [...(route.payload.message_ids ?? []), ...(route.payload.message_id ? [route.payload.message_id] : []), ...(route.payload.signal_ids ?? []).flatMap(id => signalParents.get(id) ? [signalParents.get(id)!] : [])];
    if (!payload.some(id => messageIds.has(id))) continue;
    const approved = route.approval_state === 'APPROVED';
    const confidence = route.confidence;
    if (!approved && !(confidence != null && confidence > .95 && confidence <= 1)) continue;
    for (const target of route.destinations) if (target.node_id !== sourceId && !result.has(target.node_id)) {
      const scopedMessages = messages.filter(message => payload.includes(message.id));
      if (scopedMessages.some(message => message.routingScope?.restricted && !message.routingScope.consumer_refs.some(ref =>
        ref === target.node_id || (byRef.get(ref)?.size === 1 && byRef.get(ref)?.has(target.node_id))))) continue;
      result.set(target.node_id, { nodeId: target.node_id, confidence: approved ? null : confidence ?? null,
        reason: approved ? `Freigegebene Kommunikation in ${route.route_code}` : `Gespeicherte Konfidenz ${Math.round(confidence! * 100)} % in ${route.route_code}` });
    }
  }
  return result;
}

export const RECIPIENT_DEVICE_GROUPS = ['ECUs & Gateways', 'Sensoren', 'Aktoren', 'Weitere Geräte'] as const;
export function recipientDeviceGroup(node: HardwareNode): typeof RECIPIENT_DEVICE_GROUPS[number] {
  if (node.device_type === 'SensorController') return 'Sensoren';
  if (node.device_type === 'ActuatorController') return 'Aktoren';
  if (['ECU', 'Gateway'].includes(node.device_type)) return 'ECUs & Gateways';
  return 'Weitere Geräte';
}
