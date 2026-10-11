import type { NetworkTopology } from './topology';
import type { ScenePoint, SceneBounds } from './network-scene';

export function selectionBounds(a: ScenePoint, b: ScenePoint): SceneBounds {
  return {left: Math.min(a.x, b.x), top: Math.min(a.y, b.y), width: Math.abs(b.x-a.x), height: Math.abs(b.y-a.y)};
}
export function selectNetworkArea(topology: NetworkTopology, box: SceneBounds): string[] {
  if (box.width < 6 || box.height < 6) return [];
  const contains = (x: number, y: number) => box.left <= x && x <= box.left+box.width && box.top <= y && y <= box.top+box.height;
  const selected = new Set(topology.nodes.filter(n => n.kind !== 'gateway' && contains(n.x+(n.width??168)/2, n.y+(n.height??88)/2)).map(n=>n.id));
  for (const frame of topology.scene?.frames ?? []) {
    if (contains(frame.left, frame.top) && contains(frame.left+frame.width, frame.top+frame.height)) for (const id of frame.memberIds) selected.add(id);
  }
  return [...selected].sort();
}
const names = new Intl.Collator('de', {numeric: true, sensitivity: 'base'});
export function alphabeticalTargets<T extends {id: string; label: string}>(targets: T[]): T[] {
  return [...targets].sort((a,b)=>names.compare(a.label,b.label) || a.id.localeCompare(b.id));
}
