import type { NetworkScene, ScenePoint } from './network-scene';

type Wire = {busId: string; branch: number; points: ScenePoint[]};
type Segment = {wire: number; index: number; vertical: boolean; fixed: number; lo: number; hi: number};
export type WireBridge = {busId: string; branch: number; path: string};
const EPS = .001;
const number = (value: number) => String(Math.round(value * 1000) / 1000);
const point = (x: number, y: number) => `${number(x)} ${number(y)}`;

/** Separate physical buses cross with a jump; same-bus junctions stay connected. */
export function withWireCrossings<T extends Pick<NetworkScene, 'buses'>>(scene: T): T & {wireBridges: WireBridge[]; crossingVersion: number} {
  const wires: Wire[] = [];
  for (const bus of scene.buses) {
    const ends = bus.branches.map(b => b.points.at(-1)!);
    if (!ends.length) continue;
    wires.push({busId: bus.id, branch: -1, points: [{x: ends[0].x, y: Math.min(...ends.map(p => p.y))}, {x: ends[0].x, y: Math.max(...ends.map(p => p.y))}]});
    bus.branches.forEach((b, branch) => wires.push({busId: bus.id, branch, points: b.points}));
  }
  const segments: Segment[] = [];
  wires.forEach((wire, index) => wire.points.slice(1).forEach((b, i) => {
    const a = wire.points[i], vertical = Math.abs(a.x - b.x) < EPS;
    if (!vertical && Math.abs(a.y - b.y) >= EPS) return;
    const lo = Math.min(vertical ? a.y : a.x, vertical ? b.y : b.x);
    const hi = Math.max(vertical ? a.y : a.x, vertical ? b.y : b.x);
    if (hi - lo > EPS) segments.push({wire:index, index:i, vertical, fixed:vertical?a.x:a.y, lo, hi});
  }));
  const verticals = segments.filter(s => s.vertical).sort((a,b) => a.fixed-b.fixed);
  const jumps = new Map<Segment, number[]>();
  for (const h of segments.filter(s => !s.vertical)) {
    // Binary search avoids comparing every pair in large, mostly separate clusters.
    let lo=0, hi=verticals.length;
    while (lo<hi) {const mid=(lo+hi)>>>1;if(verticals[mid].fixed<h.lo-EPS)lo=mid+1;else hi=mid;}
    for (let i=lo;i<verticals.length&&verticals[i].fixed<=h.hi+EPS;i++) {
      const v=verticals[i];
      if(wires[h.wire].busId===wires[v.wire].busId || h.fixed<v.lo-EPS || h.fixed>v.hi+EPS)continue;
      const hRoom=Math.min(v.fixed-h.lo,h.hi-v.fixed), vRoom=Math.min(h.fixed-v.lo,v.hi-h.fixed);
      // Prefer a horizontal jump. A T-touch can instead jump the vertical wire.
      const target=hRoom>3?h:vRoom>3?v:null;
      if(!target)continue; // Coincident endpoints are not an interior crossing.
      const values=jumps.get(target)??[];values.push(target.vertical?h.fixed:v.fixed);jumps.set(target,values);
    }
  }
  const gaps = new Map<string, Array<[number,number]>>();
  const wireBridges: WireBridge[] = [];
  const emitted=new Set<string>();
  for(const [segment, values] of jumps) {
    const ranges:Array<[number,number]>=[];
    for(const at of [...new Set(values)].sort((a,b)=>a-b)) {
      const radius=Math.min(6,at-segment.lo-1,segment.hi-at-1);
      const start=at-radius, end=at+radius, previous=ranges.at(-1);
      if(previous&&start<=previous[1]+2)previous[1]=Math.max(previous[1],end);else ranges.push([start,end]);
    }
    gaps.set(`${segment.wire}:${segment.index}`,ranges);
    for(const [start,end] of ranges) {
      const wire=wires[segment.wire], key=`${wire.busId}:${segment.vertical}:${number(segment.fixed)}:${number(start)}:${number(end)}`;
      if(emitted.has(key))continue;emitted.add(key);
      const half=(end-start)/2;
      const d=segment.vertical
        ? `M ${point(segment.fixed,start)} A 6 ${number(half)} 0 0 1 ${point(segment.fixed,end)}`
        : `M ${point(start,segment.fixed)} A ${number(half)} 6 0 0 1 ${point(end,segment.fixed)}`;
      wireBridges.push({busId:wire.busId,branch:wire.branch,path:d});
    }
  }
  const paths=new Map<string,string>();
  wires.forEach((wire,index)=>{
    const commands=[`M ${point(wire.points[0].x,wire.points[0].y)}`];
    wire.points.slice(1).forEach((b,i)=>{
      const a=wire.points[i],vertical=Math.abs(a.x-b.x)<EPS;
      const forward=vertical?b.y>=a.y:b.x>=a.x;
      const ranges=gaps.get(`${index}:${i}`)??[];
      for(const range of forward?ranges:[...ranges].reverse()) {
        const [start,end]=forward?range:[range[1],range[0]];
        commands.push(`L ${vertical?point(a.x,start):point(start,a.y)}`,`M ${vertical?point(a.x,end):point(end,a.y)}`);
      }
      commands.push(`L ${point(b.x,b.y)}`);
    });
    paths.set(`${wire.busId}:${wire.branch}`,commands.join(' '));
  });
  return {...scene,crossingVersion:1,wireBridges,buses:scene.buses.map(bus=>({...bus,
    displayPath:paths.get(`${bus.id}:-1`)??bus.path,
    branches:bus.branches.map((branch,index)=>({...branch,displayPath:paths.get(`${bus.id}:${index}`)??branch.path}))}))};
}
