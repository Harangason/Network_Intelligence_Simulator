import type { EngineeringObject, RoutingEntry } from './types';

export function physicalBindingStatus(item: EngineeringObject): string {
  if (!('network_ref' in item)) return 'Nicht zugeordnet';
  const binding = item.network_ref ? 'Bus zugeordnet' : 'Bus fehlt';
  const status = 'status' in item ? item.status : '';
  return ['ERROR', 'OVERLOADED', 'OUTDATED'].includes(String(status)) ? `${binding} · ${status}` : binding;
}

export function interfaceTraffic(id: string, routes: RoutingEntry[]) {
  return routes.filter(r => !['REJECTED', 'SUPERSEDED'].includes(r.status)).flatMap(route => {
    const directions = [
      ...(route.source.interface_id === id ? ['TX'] : []),
      ...(route.destinations.some(d => d.interface_id === id) ? ['RX'] : []),
    ];
    const messageIds = [...new Set([route.payload.message_id, ...(route.payload.message_ids ?? [])].filter((v): v is string => Boolean(v)))];
    return directions.map(direction => ({ route, direction, messageIds }));
  });
}

export function missingCommandSignals(message: EngineeringObject, signals: EngineeringObject[]): boolean {
  if (message.object_type !== 'Message') return false;
  const configuration = ('configuration' in message ? message.configuration : undefined) as { transport_unit?: { provenance?: { generator?: string } } } | undefined;
  const command = configuration?.transport_unit?.provenance?.generator === 'wizard-local-actuator-command';
  return command && !signals.some(s => 'message_id' in s && s.message_id === message.id);
}
