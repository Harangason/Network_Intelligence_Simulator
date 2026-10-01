"use client";

import { useState } from "react";
import { commitEngineeringImport, previewEngineeringImport } from "@/lib/engineering-api";
import { publishEngineeringModelChanged } from "@/lib/engineering-events";
import { importRoutes } from "@/lib/routing-api";
import type { EngineeringImportPlan, EngineeringImportResult } from "@/lib/types";
import { notifyWorkflowChanged } from "./workflow-header";

const IMPORT_COUNT_LABELS: Array<[keyof EngineeringImportPlan["counts"], string]> = [
  ["hardware_nodes", "Hardware"],
  ["functions", "Funktionen"],
  ["interfaces", "Interfaces"],
  ["messages", "Nachrichten"],
  ["signals", "Signale"],
];

export function EngineeringImportWizard({ onClose }: { onClose: () => void }) {
  const [plan, setPlan] = useState<EngineeringImportPlan | null>(null);
  const [result, setResult] = useState<EngineeringImportResult | null>(null);
  const [routingResult, setRoutingResult] = useState<{ fileName: string; count: number } | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");

  async function chooseFile(file: File | undefined) {
    if (!file) return;
    setAnalyzing(true);
    setError("");
    setPlan(null);
    setResult(null);
    setRoutingResult(null);
    try {
      if (file.name.toLowerCase().endsWith(".json")) {
        const parsed = JSON.parse(await file.text());
        const routes = Array.isArray(parsed) ? parsed : parsed.routes;
        if (Array.isArray(routes)) {
          const imported = await importRoutes(routes);
          setRoutingResult({ fileName: file.name, count: imported.count ?? routes.length });
          publishEngineeringModelChanged({ resource: "relations", id: "routing-json-import", name: "Routing-Import" });
          notifyWorkflowChanged();
          return;
        }
      }
      setPlan(await previewEngineeringImport(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Datei konnte nicht analysiert werden.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function runImport() {
    if (!plan) return;
    setImporting(true);
    setError("");
    try {
      const nextResult = await commitEngineeringImport(plan);
      setResult(nextResult);
      publishEngineeringModelChanged({ resource: "hardware-nodes", id: nextResult.import_id, name: "Engineering-Import" });
      notifyWorkflowChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import fehlgeschlagen.");
    } finally {
      setImporting(false);
    }
  }

  const step = result || routingResult ? 3 : plan ? 2 : 1;

  return (
    <div className="eng-import-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section aria-labelledby="import-title" aria-modal="true" className="eng-import-dialog" role="dialog">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Engineering-Import</p>
            <h2 id="import-title">Intelligenter Importer</h2>
          </div>
          <button aria-label="Import schließen" className="eng-dialog-close" onClick={onClose} type="button">×</button>
        </div>

        <div aria-label="Importschritte" className="eng-import-steps">
          {["Datei", "Vorschau", "Import"].map((label, index) => (
            <span className={step >= index + 1 ? "active" : ""} key={label}>
              {index + 1} {label}
            </span>
          ))}
        </div>

        {!plan && !result && (
          <label className="eng-import-dropzone">
            <input
              accept=".dbc,.csv,.xlsx,.json,.jsonl,.yaml,.yml,.axml,.arxml,.fibex,.xml,.asc,.trc,.log,.txt,application/json,application/xml,text/xml,text/yaml"
              disabled={analyzing}
              onChange={(event) => void chooseFile(event.target.files?.[0])}
              type="file"
            />
            <strong>{analyzing ? "Datei wird analysiert ..." : "Datei auswählen"}</strong>
            <span>DBC, CSV/XLSX, JSON/YAML, AXML/ARXML/FIBEX/XML, ASC/TRC/LOG/TXT</span>
          </label>
        )}

        {plan && !result && (
          <>
            <div className="eng-import-file">
              <div>
                <span>{plan.format.toUpperCase()}</span>
                <strong>{plan.file_name}</strong>
              </div>
              <button className="button secondary tiny" onClick={() => setPlan(null)} type="button">
                Andere Datei
              </button>
            </div>
            <div className="eng-import-counts">
              {IMPORT_COUNT_LABELS.map(([key, label]) => (
                <div key={key}>
                  <strong>{plan.counts[key]}</strong>
                  <span>{label}</span>
                </div>
              ))}
            </div>
            {Object.keys(plan.mapping).length > 0 && (
              <div className="eng-import-mapping">
                <p className="eyebrow">Erkannte Zuordnung</p>
                <dl>
                  {Object.entries(plan.mapping).map(([field, column]) => (
                    <div key={field}>
                      <dt>{column}</dt>
                      <dd>{field}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
            {plan.warnings.length > 0 && (
              <ul className="eng-import-warnings">
                {plan.warnings.map((warning) => <li key={warning}>{warning}</li>)}
              </ul>
            )}
          </>
        )}

        {result && (
          <div className="eng-import-result">
            <span className="status-badge completed">Import abgeschlossen</span>
            <strong>{result.created} Objekte angelegt</strong>
            <p>{result.reused} bereits vorhandene Objekte wurden wiederverwendet.</p>
          </div>
        )}

        {routingResult && (
          <div className="eng-import-result">
            <span className="status-badge completed">Routing-Import abgeschlossen</span>
            <strong>{routingResult.count} Routingdefinitionen importiert</strong>
            <p>{routingResult.fileName} wurde in die Routing-Tabelle übernommen.</p>
          </div>
        )}

        {error && <div className="notice error">{error}</div>}

        <div className="form-actions">
          <button className="button secondary" onClick={onClose} type="button">
            {result || routingResult ? "Schließen" : "Abbrechen"}
          </button>
          {plan && !result && (
            <button className="button primary" disabled={importing} onClick={() => void runImport()} type="button">
              {importing ? "Wird importiert ..." : "Import bestätigen"}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
