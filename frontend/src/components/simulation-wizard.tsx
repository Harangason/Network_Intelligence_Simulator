"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { createSimulation, getCatalog } from "@/lib/api";
import type { Catalog, SimulationJob, Technology } from "@/lib/types";
import { SimulationResult } from "./simulation-result";

const universalFormats = ["universal-jsonl", "universal-csv"];

export function SimulationWizard() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [domainId, setDomainId] = useState("automotive");
  const [technologyId, setTechnologyId] = useState("can_fd");
  const [formats, setFormats] = useState<string[]>(universalFormats);
  const [advanced, setAdvanced] = useState(false);
  const [advancedConfig, setAdvancedConfig] = useState(
    '{\n  "name": "custom_simulation",\n  "duration_s": 1,\n  "formats": ["universal-jsonl"]\n}',
  );
  const [job, setJob] = useState<SimulationJob | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    getCatalog()
      .then(setCatalog)
      .catch((error) =>
        setCatalogError(
          error instanceof Error
            ? error.message
            : "Technologiekatalog konnte nicht geladen werden.",
        ),
      );
  }, []);

  const domain = useMemo(
    () => catalog?.domains.find((item) => item.id === domainId),
    [catalog, domainId],
  );
  const technology = useMemo(
    () => domain?.technologies.find((item) => item.id === technologyId),
    [domain, technologyId],
  );
  const availableFormats = useMemo(
    () =>
      Array.from(
        new Set([...universalFormats, ...(technology?.native_formats ?? [])]),
      ),
    [technology],
  );

  function chooseDomain(value: string) {
    setDomainId(value);
    const nextDomain = catalog?.domains.find((item) => item.id === value);
    const nextTechnology = nextDomain?.technologies[0];
    if (nextTechnology) {
      setTechnologyId(nextTechnology.id);
      setFormats(universalFormats);
    }
  }

  function chooseTechnology(value: string) {
    setTechnologyId(value);
    setFormats(universalFormats);
  }

  function toggleFormat(format: string) {
    setFormats((current) =>
      current.includes(format)
        ? current.filter((item) => item !== format)
        : [...current, format],
    );
  }

  async function submit(formElement: HTMLFormElement, validateOnly: boolean) {
    setSubmitting(true);
    setFormError("");
    try {
      const form = new FormData(formElement);
      let payload: Record<string, unknown>;
      if (advanced) {
        payload = { config: JSON.parse(advancedConfig) };
      } else {
        payload = {
          industry: domainId,
          technology: technologyId,
          node_count: Number(form.get("node_count")),
          duration_s: Number(form.get("duration_s")),
          cycle_ms: Number(form.get("cycle_ms")),
          bitrate: Number(form.get("bitrate")),
          payload_bytes: Number(form.get("payload_bytes")),
          seed: Number(form.get("seed")),
          max_events: Number(form.get("max_events")),
          dropout_probability: Number(form.get("dropout_probability")),
          corruption_probability: Number(form.get("corruption_probability")),
          formats,
        };
      }
      const nextJob = await createSimulation(payload, validateOnly);
      setJob(nextJob);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Anfrage fehlgeschlagen.");
    } finally {
      setSubmitting(false);
    }
  }

  if (catalogError) {
    return (
      <div className="panel error-card">
        <p className="eyebrow">Backend nicht erreichbar</p>
        <h2>{catalogError}</h2>
        <p className="muted">
          Starte die Anwendung mit dem gemeinsamen Web-Launcher.
        </p>
      </div>
    );
  }
  if (!catalog || !domain || !technology) {
    return <div className="panel loading-panel">Technologiekatalog wird geladen …</div>;
  }

  return (
    <div className="workspace-grid">
      <form
        className="panel config-panel"
        onSubmit={(event: FormEvent<HTMLFormElement>) => {
          event.preventDefault();
          void submit(event.currentTarget, false);
        }}
      >
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Neue Simulation</p>
            <h2>Konfiguration</h2>
          </div>
          <label className="mode-switch">
            <input
              checked={advanced}
              onChange={(event) => setAdvanced(event.target.checked)}
              type="checkbox"
            />
            <span>JSON-Modus</span>
          </label>
        </div>

        {advanced ? (
          <div className="field full-width">
            <label htmlFor="advanced_config">Vollständige Konfiguration</label>
            <textarea
              className="json-editor"
              id="advanced_config"
              onChange={(event) => setAdvancedConfig(event.target.value)}
              spellCheck={false}
              value={advancedConfig}
            />
            <small>
              Der Ausgabeordner wird aus Sicherheitsgründen vom Backend festgelegt.
            </small>
          </div>
        ) : (
          <>
            <div className="section-title">
              <span>01</span>
              Technologie
            </div>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="domain">Anwendungsbereich</label>
                <select
                  id="domain"
                  onChange={(event) => chooseDomain(event.target.value)}
                  value={domainId}
                >
                  {catalog.domains.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="technology">Bus / Protokoll</label>
                <select
                  id="technology"
                  onChange={(event) => chooseTechnology(event.target.value)}
                  value={technologyId}
                >
                  {domain.technologies.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.id.replaceAll("_", " ").toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <TechnologyCard technology={technology} />

            <div className="section-title">
              <span>02</span>
              Netzwerkparameter
            </div>
            <div className="form-grid three">
              <NumberField label="Knoten" name="node_count" min="2" max="100" value="2" />
              <NumberField
                label="Bitrate (bit/s)"
                name="bitrate"
                min="1"
                value={String(technology.default_bitrate ?? 1000000)}
              />
              <NumberField
                label="Payload (Byte)"
                name="payload_bytes"
                min="0"
                max={String(technology.max_payload_bytes ?? 65535)}
                value={String(Math.min(8, technology.max_payload_bytes ?? 8))}
              />
              <NumberField label="Dauer (s)" name="duration_s" min="0.001" step="0.001" value="1" />
              <NumberField label="Zyklus (ms)" name="cycle_ms" min="0.001" step="0.001" value="100" />
              <NumberField label="Seed" name="seed" min="0" value="42" />
              <NumberField label="Max. Events" name="max_events" min="1" value="100000" />
              <NumberField
                label="Dropout"
                name="dropout_probability"
                min="0"
                max="1"
                step="0.001"
                value="0"
              />
              <NumberField
                label="Korruption"
                name="corruption_probability"
                min="0"
                max="1"
                step="0.001"
                value="0"
              />
            </div>

            <div className="section-title">
              <span>03</span>
              Ausgabeformate
            </div>
            <div className="format-grid">
              {availableFormats.map((format) => (
                <label
                  className={`format-option ${formats.includes(format) ? "selected" : ""}`}
                  key={format}
                >
                  <input
                    checked={formats.includes(format)}
                    onChange={() => toggleFormat(format)}
                    type="checkbox"
                  />
                  <span>{format}</span>
                  <small>
                    {format.startsWith("universal") ? "Universell" : "Nativ"}
                  </small>
                </label>
              ))}
            </div>
          </>
        )}

        {formError && <div className="notice error">{formError}</div>}

        <div className="form-actions">
          <button
            className="button secondary"
            disabled={submitting}
            onClick={(event) => {
              event.preventDefault();
              if (event.currentTarget.form) {
                void submit(event.currentTarget.form, true);
              }
            }}
            type="button"
          >
            Nur validieren
          </button>
          <button
            className="button primary"
            disabled={submitting || (!advanced && formats.length === 0)}
            type="submit"
          >
            {submitting ? "Wird gestartet …" : "Simulation starten →"}
          </button>
        </div>
      </form>

      <aside className="side-column">
        <div className="panel overview-panel">
          <p className="eyebrow">Run overview</p>
          <h2>{technology.id.replaceAll("_", " ").toUpperCase()}</h2>
          <dl className="overview-list">
            <div>
              <dt>Bereich</dt>
              <dd>{domain.label}</dd>
            </div>
            <div>
              <dt>Medium</dt>
              <dd>{technology.medium}</dd>
            </div>
            <div>
              <dt>Topologie</dt>
              <dd>{technology.topology}</dd>
            </div>
            <div>
              <dt>Formate</dt>
              <dd>{formats.length}</dd>
            </div>
          </dl>
        </div>

        {job ? (
          <>
            <SimulationResult jobId={job.id} />
            <Link className="job-link" href={`/simulations/${job.id}`}>
              Ergebnis in eigener Ansicht öffnen ↗
            </Link>
          </>
        ) : (
          <div className="empty-result">
            <span className="empty-icon">⌁</span>
            <strong>Noch kein Lauf gestartet</strong>
            <p>Validierung und Trace-Statistiken erscheinen hier.</p>
          </div>
        )}
      </aside>
    </div>
  );
}

function NumberField({
  label,
  name,
  value,
  ...props
}: {
  label: string;
  name: string;
  value: string;
  min?: string;
  max?: string;
  step?: string;
}) {
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      <input defaultValue={value} id={name} name={name} type="number" {...props} />
    </div>
  );
}

function TechnologyCard({ technology }: { technology: Technology }) {
  return (
    <div className="technology-card">
      <div className="technology-symbol">⌁</div>
      <div>
        <strong>{technology.family}</strong>
        <span>
          {technology.kind} · {technology.medium} · {technology.topology}
        </span>
      </div>
      <span className="tag">
        max. {(technology.max_payload_bytes ?? 0).toLocaleString("de-DE")} B
      </span>
    </div>
  );
}
