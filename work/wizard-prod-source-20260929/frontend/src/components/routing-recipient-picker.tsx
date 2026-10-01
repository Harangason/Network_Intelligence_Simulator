'use client';

import type { HardwareNode } from '@/lib/types';
import { RECIPIENT_DEVICE_GROUPS, recipientDeviceGroup, type RecipientRecommendation } from '@/lib/routing-recipient-recommendations';

export function RoutingRecipientPicker({ options, allNodes, selectedIds, recommendations, onToggle }: {
  options: HardwareNode[]; allNodes: HardwareNode[]; selectedIds: string[];
  recommendations: Map<string, RecipientRecommendation>; onToggle: (id: string) => void;
}) {
  const selected = new Set(selectedIds);
  const lists = [
    { title: 'Empfohlen', rows: options.filter(node => !selected.has(node.id) && recommendations.has(node.id)), empty: 'Keine belegte Empfehlung für diese Suche.' },
    { title: 'Übrige', rows: options.filter(node => !selected.has(node.id) && !recommendations.has(node.id)), empty: 'Keine weiteren Treffer.' },
    { title: 'Ausgewählt', rows: allNodes.filter(node => selected.has(node.id)), empty: 'Noch kein Empfänger ausgewählt.' },
  ];
  return <section className="routing-recipient-picker full-width" aria-label="Empfänger auswählen">
    <p>Empfohlen werden belegte Kommunikationspartner oder vorhandene Vorschläge mit einer gespeicherten Konfidenz über 95 %. Die übrigen Geräte stehen alphabetisch je Gerätetyp bereit. Ausgewählte Empfänger bleiben auch bei einer Suche sichtbar.</p>
    <div className="routing-recipient-columns">{lists.map(list => <section key={list.title} aria-label={list.title}>
      <h3>{list.title} <span>{list.rows.length}</span></h3>
      <div className="routing-recipient-list" tabIndex={0} aria-label={`${list.title} durchsuchen`}>
        {!list.rows.length && <p>{list.empty}</p>}
        {RECIPIENT_DEVICE_GROUPS.map(group => {
          const rows = list.rows.filter(node => recipientDeviceGroup(node) === group).sort((a, b) => a.name.localeCompare(b.name, 'de') || a.id.localeCompare(b.id));
          return rows.length ? <fieldset key={group}><legend>{group}</legend>{rows.map(node => <label key={node.id}>
            <input type="checkbox" checked={selected.has(node.id)} onChange={() => onToggle(node.id)} />
            <span><strong>{node.name}</strong><small>{recommendations.get(node.id)?.reason ?? node.device_type}</small></span>
          </label>)}</fieldset> : null;
        })}
      </div>
    </section>)}</div>
  </section>;
}
