import type { EngineeringObject } from './types';

export function conciseGeneratedName(kind: string, name: string): string {
  if (kind === 'Function') return name.replace(/_(?:Sensor_Erfassung|Actuator_Steuerung|Gateway_Kommunikation|Steuerung)$/, '') || name;
  if (kind === 'Interface') return name.replace(/_1$/, '') || name;
  if (kind === 'Message') return name
    .replace(/(?:Sensor_?Erfassung|Actuator_?Steuerung|Gateway_?Kommunikation|Steuerung)?_?Data(?=\d*$)/, '')
    .replace(/_Command$/, ' Befehl')
    .replace(/([a-zäöüß0-9])([A-ZÄÖÜ])/g, '$1 $2')
    .replace(/[_\s]+/g, ' ').trim() || name;
  return name;
}

export function technologyLabel(value: string): string {
  return ({ CAN_FD: 'CAN-FD', CAN: 'CAN', LIN: 'LIN', ETHERNET: 'Ethernet', FLEXRAY: 'FlexRay',
    AUTOMOTIVE_ETHERNET: 'Automotive Ethernet', CAN_XL: 'CAN XL' } as Record<string, string>)[value.toUpperCase()] ?? value;
}

export function messageBusNames(message: EngineeringObject, objects: Map<string, EngineeringObject>, names: Record<string, string>): string {
  if (!('hardware_interface_id' in message)) return 'Nicht zugeordnet';
  const bindings = (message.configuration as { physical_transmit_bindings?: { hardware_interface_id?: string }[] } | undefined)?.physical_transmit_bindings ?? [];
  const ids = [message.hardware_interface_id, ...bindings.map(binding => binding.hardware_interface_id)];
  const buses = new Set(ids.flatMap(id => {
    const port = id ? objects.get(id) : undefined;
    return port && 'network_ref' in port && typeof port.network_ref === 'string' && port.network_ref ? [names[port.network_ref] ?? port.network_ref] : [];
  }));
  return buses.size ? [...buses].join(', ') : 'Nicht zugeordnet';
}
