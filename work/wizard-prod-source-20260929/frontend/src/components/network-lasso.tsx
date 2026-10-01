"use client";
import { useRef, useState } from 'react';
import { selectNetworkArea, selectionBounds } from '@/lib/network-selection';
import type { NetworkTopology } from '@/lib/topology';
import type { ScenePoint } from '@/lib/network-scene';

export function NetworkLasso({topology, zoom, onSelect}: {topology: NetworkTopology; zoom: number; onSelect: (ids:string[])=>void}) {
  const start = useRef<ScenePoint|null>(null);
  const [end, setEnd] = useState<ScenePoint|null>(null);
  const box = start.current && end ? selectionBounds(start.current,end) : null;
  return <div className="net-lasso-layer" aria-label="Bereich zum Zuordnen markieren"
    onPointerDown={event=>{if(event.button!==0)return;event.preventDefault();event.stopPropagation();event.currentTarget.setPointerCapture(event.pointerId);const r=event.currentTarget.getBoundingClientRect();start.current={x:(event.clientX-r.left)/zoom,y:(event.clientY-r.top)/zoom};setEnd(start.current);}}
    onPointerMove={event=>{if(!start.current)return;event.stopPropagation();const r=event.currentTarget.getBoundingClientRect();setEnd({x:(event.clientX-r.left)/zoom,y:(event.clientY-r.top)/zoom});}}
    onPointerUp={event=>{event.stopPropagation();if(!start.current)return;const r=event.currentTarget.getBoundingClientRect();const selected=selectNetworkArea(topology,selectionBounds(start.current,{x:(event.clientX-r.left)/zoom,y:(event.clientY-r.top)/zoom}));start.current=null;setEnd(null);onSelect(selected);}}
    onPointerCancel={()=>{start.current=null;setEnd(null);}}>
    {box && <div className="net-lasso-rectangle" style={{left:box.left,top:box.top,width:box.width,height:box.height}}/>}
  </div>;
}
