"use client";

import { useId, useMemo, useRef, useState } from 'react';
import { searchNetworkEntries, type NetworkSearchEntry } from '@/lib/network-editor-search';

export function NetworkEditorSearch({ entries, query, onQueryChange, onSelect }: {
  entries: NetworkSearchEntry[];
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (entry: NetworkSearchEntry) => void;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const results = useMemo(() => searchNetworkEntries(entries, query), [entries, query]);
  const active = Math.max(0, results.findIndex(result => result.key === activeKey));
  const expanded = open && Boolean(query.trim());
  function select(entry: NetworkSearchEntry) {
    onSelect(entry);
    setOpen(false);
    input.current?.focus({ preventScroll: true });
  }
  function navigate(index: number) {
    setOpen(true);
    const next = results[index];
    if (!next) return;
    setActiveKey(next.key);
    requestAnimationFrame(() => {
      const row = list.current?.children[index] as HTMLElement | undefined;
      if (!row || !list.current) return;
      // Scroll only the results, never the page or the network canvas.
      const top = row.offsetTop - list.current.offsetTop;
      if (top < list.current.scrollTop) list.current.scrollTop = top;
      else if (top + row.offsetHeight > list.current.scrollTop + list.current.clientHeight)
        list.current.scrollTop = top + row.offsetHeight - list.current.clientHeight;
    });
  }
  return <div className="net-search" onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
  }}>
    <div className="net-search-field">
      <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8" cy="8" r="5.5" /><path d="m12 12 5 5" /></svg>
      <input ref={input} type="search" role="combobox" aria-label="Netzwerk durchsuchen"
        aria-expanded={expanded} aria-controls={expanded ? `${id}-results` : undefined} aria-autocomplete="list"
        aria-activedescendant={expanded && results.length ? `${id}-${active}` : undefined}
        autoComplete="off" placeholder="Gerät, Bus oder Anschluss suchen …" value={query}
        onFocus={() => setOpen(true)} onClick={() => setOpen(true)}
        onChange={event => { onQueryChange(event.target.value); setActiveKey(null); setOpen(true); }}
        onKeyDown={event => {
          if (event.key === 'Enter') {
            event.preventDefault(); event.stopPropagation();
            if (results[active]) select(results[active]);
          } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault(); event.stopPropagation();
            navigate(!expanded ? 0 : (active + (event.key === 'ArrowDown' ? 1 : -1) + results.length) % Math.max(1, results.length));
          } else if (event.key === 'Escape') {
            event.preventDefault(); event.stopPropagation(); setOpen(false);
          }
        }} />
      {query && <button type="button" aria-label="Netzwerksuche leeren" onClick={() => {
        onQueryChange(''); setActiveKey(null); input.current?.focus({ preventScroll: true });
      }}>×</button>}
    </div>
    {expanded && <div className="net-search-popover">
      <p role="status">{results.length ? `${results.length} Treffer · Auswählen zum Zentrieren` : 'Keine Treffer. Anderen Geräte-, Bus- oder Anschlussnamen versuchen.'}</p>
      <div id={`${id}-results`} ref={list} role="listbox" aria-label="Netzwerktreffer" className="net-search-results">
        {results.map((result, index) => <button type="button" role="option" tabIndex={-1}
          id={`${id}-${index}`} key={result.key} aria-selected={index === active}
          data-search-kind={result.kind} data-search-id={result.id}
          onPointerDown={event => event.preventDefault()} onClick={() => select(result)}>
          <strong>{result.name}</strong><span>{result.detail}</span>
        </button>)}
      </div>
    </div>}
  </div>;
}
