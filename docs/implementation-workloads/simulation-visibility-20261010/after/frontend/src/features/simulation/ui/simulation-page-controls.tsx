"use client";

export function SimulationPageControls({ label, page, pageCount, first, last, total, onPage }: {
  label: string; page: number; pageCount: number; first: number; last: number; total: number;
  onPage: (page: number) => void;
}) {
  if (pageCount <= 1) return null;
  return <nav className="simulation-page-controls" aria-label={`${label} durchblättern`}>
    <output aria-live="polite">{label} {first}–{last} von {total}</output>
    <button type="button" className="button secondary tiny" disabled={page === 0} onClick={() => onPage(page - 1)}>Zurück</button>
    <label>Seite <select aria-label={`${label}: Seite auswählen`} value={page} onChange={event => onPage(Number(event.target.value))}>
      {Array.from({ length: pageCount }, (_, index) => <option key={index} value={index}>{index + 1} / {pageCount}</option>)}
    </select></label>
    <button type="button" className="button secondary tiny" disabled={page + 1 === pageCount} onClick={() => onPage(page + 1)}>Weiter</button>
  </nav>;
}
