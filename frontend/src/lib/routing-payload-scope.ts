import type { EngInterface, EngMessage } from './types';

export type MessageScope = {
  scope: string; restricted: boolean; consumer_refs: string[]; reason: string;
  routing_enabled?: boolean; forwarding_enabled?: boolean; blocked_signal_ids?: string[]; local?: boolean;
};
export type ScopedMessage = EngMessage & { routingScope?: MessageScope };

export function messageAllowsDestination(message: ScopedMessage, nodeId: string, interfaceId: string, interfaces: EngInterface[]) {
  const scope = message.routingScope;
  if (!scope) return false; // Wait for the authoritative project-scoped contract.
  if (!scope.restricted) return true;
  const iface = interfaces.find(i => i.id === interfaceId && i.hardware_node_id === nodeId);
  return [nodeId, iface?.id, iface?.function_id].some(id => !!id && scope.consumer_refs.includes(id));
}

export function payloadScopeConflicts(messages: ScopedMessage[], destinations: string[], interfaceIds: Record<string, string>, interfaces: EngInterface[]) {
  return messages.filter(m => destinations.some(id => !messageAllowsDestination(m, id, interfaceIds[id] ?? '', interfaces)));
}
