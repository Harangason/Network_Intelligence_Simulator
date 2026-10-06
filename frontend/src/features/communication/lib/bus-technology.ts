import type { BusType } from "../../network/lib/topology";
import projection from './technology-projection.json' with { type: 'json' };

// Editor choices are UI capabilities; aliases and technical values are generated.
export const editorBusTypes = ['can', 'can_fd', 'can_xl', 'lin', 'automotive_ethernet', 'flexray',
  'i2c', 'spi', 'uart', 'modbus_rtu', 'modbus_tcp', 'gpio', 'pwm', 'adc', 'dac'] as const;
const token = (value: string) => value.trim().toLowerCase().replace(/[- /]+/g, '_');
const identities = new Map(projection.technologies.flatMap(item =>
  [item.id, ...item.aliases].map(alias => [token(alias), item.id] as const)));

/** Resolve a confirmed technology. A network name carries no technology evidence. */
export function routingBusType(protocol?: string | null, _networkId?: string | null): BusType | null {
  if (!protocol?.trim()) return null;
  const canonical = identities.get(token(protocol));
  if (!canonical) return null;
  const editorKey = canonical === 'ethernet' ? 'automotive_ethernet' : canonical;
  return editorBusTypes.includes(editorKey as BusType) ? editorKey as BusType : null;
}
