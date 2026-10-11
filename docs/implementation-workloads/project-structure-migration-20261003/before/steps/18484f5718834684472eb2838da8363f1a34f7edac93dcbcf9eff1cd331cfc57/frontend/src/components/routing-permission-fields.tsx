"use client";

import { useId } from "react";

export function RoutingPermissionFields({ enabled, onChange, parentDisabled = false, signal = false }: {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  parentDisabled?: boolean;
  signal?: boolean;
}) {
  const hintId = useId();
  return (
    <fieldset className="eng-requirement-fields eng-routing-permission">
      <legend>Systemübergreifende Weiterleitung</legend>
      <button aria-checked={enabled} aria-describedby={hintId} aria-label="Geroutet" className={`button ${enabled ? "primary" : "secondary"}`} onClick={() => onChange(!enabled)} role="switch" type="button">
        Geroutet: {enabled ? "On" : "Off"}
      </button>
      <p className="muted" id={hintId}>
        {enabled ? "Für bestätigte Empfänger zur Weiterleitung freigegeben. Die Auswahl erzeugt keine neue Route." : "Bleibt lokal beim zugeordneten System. Keine Weiterleitung an fremde Systeme."}
        {" "}Lokale Sensor- und Aktorkommunikation mit Buslast und Timing bleibt erhalten.
      </p>
      {parentDisabled && <p className="notice warning">Die übergeordnete Nachricht steht auf Off und sperrt die Weiterleitung dieses Signals auch bei On.</p>}
      {signal && <p className="muted">Ein Signal auf Off sperrt die externe Weitergabe seiner gesamten Nachricht. Für andere, externe Signale ist eine getrennte Nachricht mit eigener Codierung erforderlich; die DLC wird nicht automatisch verkürzt.</p>}
    </fieldset>
  );
}
