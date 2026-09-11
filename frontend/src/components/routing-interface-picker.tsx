'use client';

import { useId, useState } from 'react';
import type { RoutingInterface } from '@/lib/routing-network-context';
import { interfaceBindingLabel } from '@/lib/routing-network-context';
import { endpointInterfaceChoices } from '@/lib/routing-interface-search';
import type { HardwareNode } from '@/lib/types';

export function RoutingInterfacePicker({ label, nodeId, neighborId = '', interfaces, protocol, value, onPick }: {
  label: string; nodeId: string; neighborId?: string; interfaces: RoutingInterface[]; protocol: string; value: string; onPick: (id: string) => void;
}) {
  const [query, setQuery] = useState('');
  const id = useId();
  const choices = endpointInterfaceChoices(interfaces, nodeId, neighborId, protocol, query);
  const selected = interfaces.find(i => i.id === value && i.hardware_node_id === nodeId);
  const optionLabel = (item: RoutingInterface) => `${item.name} · ${item.interface_type} · ${interfaceBindingLabel(item)}`;
  return <div className="routing-interface-picker">
    <label htmlFor={`${id}-search`}>{label} suchen</label>
    <input id={`${id}-search`} type="search" value={query} placeholder="Name, Technik oder Bus …" onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') e.preventDefault(); }} />
    <label htmlFor={id}>{label}</label>
    <select id={id} value={value} onChange={e => onPick(e.target.value)}>
      <option value="">Bitte Schnittstelle wählen</option>
      {value && !choices.some(c => c.item.id === value) && <option value={value}>{selected ? `${optionLabel(selected)} · aktuelle Auswahl` : `Unbekannt · ${value}`}</option>}
      {[true, false].map(shared => <optgroup key={String(shared)} label={shared ? 'Am Bus des nächsten Pfadknotens' : 'Weitere Schnittstellen'}>
        {choices.filter(c => Boolean(c.common.length) === shared).map(({ item }) => <option key={item.id} value={item.id}>{optionLabel(item)}</option>)}
      </optgroup>)}
    </select>
    <small>{choices.length} Treffer · Buszuordnung vor Protokollähnlichkeit. Ein gemeinsamer Bus ersetzt keine Pfadprüfung.</small>
  </div>;
}

export function RoutingPathPreview({ sourceId, destinationIds, gatewayIds, sourceNetwork, destinationNetworks, hardware, interfaces }: {
  sourceId: string; destinationIds: string[]; gatewayIds: string[]; sourceNetwork: string; destinationNetworks: Record<string, string>; hardware: HardwareNode[]; interfaces: RoutingInterface[];
}) {
  const name = (id: string) => hardware.find(n => n.id === id)?.name ?? id;
  const buses = (nodeId: string) => interfaces.filter(i => i.hardware_node_id === nodeId).flatMap(i => i.physicalBindings ?? []);
  return <section className="routing-path-preview full-width" aria-label="Kommunikationsstrecke">
    <strong>Geplante Strecke · {gatewayIds.length ? 'Sender → Gateway → Empfänger' : 'Sender → Empfänger'}</strong>
    {!destinationIds.length && <p>Zuerst Sender und Empfänger wählen.</p>}
    {destinationIds.map(target => {
      const nodes = [sourceId, ...gatewayIds, target];
      return <div key={target}><h4>{nodes.map(name).join(' → ')}</h4><ol>{nodes.slice(0, -1).map((left, index) => {
        const right = nodes[index + 1];
        const leftBuses = buses(left), rightBuses = buses(right);
        const common = [...new Map(leftBuses.filter(b => rightBuses.some(r => r.id === b.id)).map(b => [b.id, b])).values()];
        const sourceMismatch = index === 0 && sourceNetwork && !common.some(b => b.id === sourceNetwork);
        const targetMismatch = index === nodes.length - 2 && destinationNetworks[target] && !common.some(b => b.id === destinationNetworks[target]);
        return <li key={`${left}:${right}`}><span>{name(left)} → {name(right)}</span><small>{common.length ? common.map(b => `${b.name} · ${b.protocol}`).join(' / ') : 'Kein gemeinsamer physischer Bus nachgewiesen'}{sourceMismatch || targetMismatch ? ' · Gewählte Schnittstelle/Bus prüfen' : ''}</small></li>;
      })}</ol></div>;
    })}
    <small>Gespeicherte Gateway-Reihenfolge und aktuelle Anschlusszuordnung. Die vollständige technische Prüfung erfolgt beim Validieren.</small>
  </section>;
}
