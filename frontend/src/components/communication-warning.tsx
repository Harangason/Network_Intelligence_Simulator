"use client";

import { useRef } from "react";
import { communicationWarningText, type CommunicationWarning } from "@/lib/communication-warnings";

export function CommunicationWarningIndicator({ name, issues }: { name: string; issues: CommunicationWarning[] }) {
  const dialog = useRef<HTMLDialogElement>(null);
  if (!issues.length) return <span className="muted">—</span>;
  return <>
    <button type="button" className="eng-communication-warning" aria-label={`Kommunikationswarnungen für ${name}`}
      title={communicationWarningText(issues)} onClick={event => { event.stopPropagation(); dialog.current?.showModal(); }}>
      <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 3 22 21H2Z" /><path d="M12 9v5m0 3v1" /></svg>
      <span>{issues.length}</span>
    </button>
    <dialog ref={dialog} className="eng-communication-warning-dialog" aria-label={`Kommunikationswarnungen: ${name}`}
      onClick={event => event.stopPropagation()} onKeyDown={event => event.stopPropagation()}>
      <header><h3>Kommunikationswarnungen · {name}</h3><button type="button" className="button secondary tiny" aria-label="Warnungen schließen" onClick={() => dialog.current?.close()}>×</button></header>
      <p>Abgleich mit den aktuellen Anschlüssen, Buszuordnungen und Routen. Betroffene Bewertungen müssen nach der Korrektur erneut berechnet und geprüft werden.</p>
      <ul>{issues.map(issue => <li key={issue.key}>
        {(issue.routeCode || issue.messageName) && <strong>{[issue.routeCode, issue.messageName].filter(Boolean).join(" · ")}</strong>}
        <p>{issue.reason}</p>
        <small>Betroffen: {issue.fields.join(" · ")}</small>
      </li>)}</ul>
    </dialog>
  </>;
}
