"use client";

import { useEffect, useMemo, useState } from "react";
import {
  analyzeEcuStructureTransfer,
  applyEcuStructureTransfer,
  rejectEcuStructureTransfer,
} from "@/lib/engineering-api";
import {
  engineeringObjectTypeClass,
  engineeringObjectTypeLabel,
} from "@/lib/engineering-object-style";
import type {
  EcuTransferAnalysis,
  EcuTransferDecision,
  EcuTransferItem,
  EngineeringObject,
} from "@/lib/types";

function isEcu(item: EngineeringObject) {
  return ("device_type" in item && ["ECU", "EmbeddedController"].includes(item.device_type))
    || item.name.toLocaleLowerCase("de-DE").includes("ecu");
}

export function EcuStructureTransferDialog({
  hardware,
  onClose,
  onChanged,
}: {
  hardware: EngineeringObject[];
  onClose: () => void;
  onChanged: (message: string) => Promise<void>;
}) {
  const ecuNodes = useMemo(
    () => hardware.filter(isEcu).sort((left, right) => left.name.localeCompare(right.name, "de")),
    [hardware],
  );
  const [sourceId, setSourceId] = useState(ecuNodes[0]?.id ?? "");
  const [targetIds, setTargetIds] = useState<string[]>(() => ecuNodes.slice(1).map((item) => item.id));
  const [targetFilter, setTargetFilter] = useState("");
  const [analysis, setAnalysis] = useState<EcuTransferAnalysis | null>(null);
  const [reviewIndex, setReviewIndex] = useState(0);
  const [applied, setApplied] = useState(0);
  const [rejected, setRejected] = useState(0);
  const [created, setCreated] = useState(0);
  const [reused, setReused] = useState(0);
  const [skipped, setSkipped] = useState(0);
  const [decisions, setDecisions] = useState<Record<string, Record<string, EcuTransferDecision>>>({});
  const [editingKey, setEditingKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    setTargetIds(ecuNodes.filter((item) => item.id !== sourceId).map((item) => item.id));
  }, [ecuNodes, sourceId]);

  const normalizedFilter = targetFilter.trim().toLocaleLowerCase("de-DE");
  const visibleTargets = ecuNodes.filter((item) => (
    item.id !== sourceId && item.name.toLocaleLowerCase("de-DE").includes(normalizedFilter)
  ));
  const current = analysis?.targets[reviewIndex] ?? null;

  function toggleTarget(id: string) {
    setTargetIds((currentIds) => currentIds.includes(id)
      ? currentIds.filter((currentId) => currentId !== id)
      : [...currentIds, id]);
  }

  async function analyze() {
    if (!sourceId || !targetIds.length) return;
    setBusy(true);
    setError("");
    try {
      const result = await analyzeEcuStructureTransfer(sourceId, targetIds);
      setAnalysis(result);
      setReviewIndex(0);
      setDecisions(Object.fromEntries(result.targets.map((target) => [
        target.proposal_id,
        Object.fromEntries(target.items.map((item) => [item.plan_key, {
          plan_key: item.plan_key,
          action: item.action,
          recommended_name: item.recommended_name,
          ...(item.target_id ? { target_id: item.target_id } : {}),
        } satisfies EcuTransferDecision])),
      ])));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Die ECU-Struktur konnte nicht analysiert werden.");
    } finally {
      setBusy(false);
    }
  }

  async function decide(accept: boolean) {
    if (!analysis || !current) return;
    setBusy(true);
    setError("");
    try {
      if (accept) {
        const result = await applyEcuStructureTransfer(
          current.proposal_id,
          current.items.map((item) => decisionFor(item)),
        );
        setApplied((value) => value + 1);
        setCreated((value) => value + result.created);
        setReused((value) => value + result.reused);
        setSkipped((value) => value + result.skipped);
      } else {
        await rejectEcuStructureTransfer(current.proposal_id);
        setRejected((value) => value + 1);
      }
      if (reviewIndex + 1 >= analysis.targets.length) {
        setDone(true);
      } else {
        setReviewIndex((value) => value + 1);
      }
      setEditingKey("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Die Entscheidung konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    if (applied) {
      await onChanged(`${applied} ECU-Strukturen übernommen: ${created} neu angelegt, ${reused} vorhandene Objekte genutzt, ${skipped} ausgelassen; ${rejected} ECUs abgelehnt.`);
    }
    onClose();
  }

  function decisionFor(item: EcuTransferItem): EcuTransferDecision {
    if (current) {
      const decision = decisions[current.proposal_id]?.[item.plan_key];
      if (decision) return decision;
    }
    return {
      plan_key: item.plan_key,
      action: item.action,
      recommended_name: item.recommended_name,
      ...(item.target_id ? { target_id: item.target_id } : {}),
    };
  }

  function updateDecision(item: EcuTransferItem, updates: Partial<EcuTransferDecision>) {
    if (!current) return;
    setDecisions((currentDecisions) => {
      const proposalDecisions = currentDecisions[current.proposal_id] ?? {};
      const previous = proposalDecisions[item.plan_key] ?? decisionFor(item);
      const next = { ...previous, ...updates };
      if (next.action !== "reuse") delete next.target_id;
      if (next.action === "reuse" && item.target_id) next.target_id = item.target_id;
      return {
        ...currentDecisions,
        [current.proposal_id]: { ...proposalDecisions, [item.plan_key]: next },
      };
    });
  }

  const currentDecisions = current?.items.map((item) => ({ item, decision: decisionFor(item) })) ?? [];
  const decisionSummary = currentDecisions.reduce((summary, entry) => {
    summary[entry.decision.action] += 1;
    return summary;
  }, { create: 0, reuse: 0, skip: 0 });
  const hasInvalidName = currentDecisions.some(({ decision }) => (
    decision.action === "create" && !decision.recommended_name?.trim()
  ));

  return (
    <div className="proposal-wizard-backdrop ecu-transfer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && void finish()} role="presentation">
      <section aria-modal="true" className="proposal-wizard ecu-transfer-dialog" role="dialog">
        <header>
          <div>
            <p className="eyebrow">KI-Strukturtransfer</p>
            <h3>{analysis ? "ECU einzeln prüfen" : "Referenzstruktur analysieren"}</h3>
            <span>{analysis ? `${reviewIndex + 1} von ${analysis.targets.length} Ziel-ECUs` : "Eine Referenz-ECU auf ausgewählte Ziel-ECUs übertragen."}</span>
          </div>
          <button aria-label="KI-Strukturtransfer schließen" className="eng-dialog-close" disabled={busy} onClick={() => void finish()} type="button">×</button>
        </header>

        {!analysis && !done && (
          <div className="ecu-transfer-config">
            <label className="ecu-transfer-source">
              <span>Referenz-ECU</span>
              <select onChange={(event) => setSourceId(event.target.value)} value={sourceId}>
                {ecuNodes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <div className="ecu-transfer-target-header">
              <label><span>Ziel-ECUs filtern</span><input onChange={(event) => setTargetFilter(event.target.value)} placeholder="ECU-Name" type="search" value={targetFilter} /></label>
              <span>{targetIds.length} ausgewählt</span>
            </div>
            <div className="ecu-transfer-target-actions">
              <button className="button secondary tiny" onClick={() => setTargetIds((currentIds) => Array.from(new Set([...currentIds, ...visibleTargets.map((item) => item.id)])))} type="button">Sichtbare auswählen</button>
              <button className="button secondary tiny" onClick={() => setTargetIds((currentIds) => currentIds.filter((id) => !visibleTargets.some((item) => item.id === id)))} type="button">Sichtbare abwählen</button>
            </div>
            <div className="ecu-transfer-target-list">
              {visibleTargets.map((item) => <label className={`eng-object-surface eng-type-hardwarenode ${targetIds.includes(item.id) ? "selected" : ""}`} key={item.id}><input checked={targetIds.includes(item.id)} onChange={() => toggleTarget(item.id)} type="checkbox" /><span><strong>{item.name}</strong><small>{"device_type" in item ? item.device_type : "ECU"}</small></span></label>)}
              {!visibleTargets.length && <div className="eng-proposal-empty">Keine passenden Ziel-ECUs.</div>}
            </div>
          </div>
        )}

        {analysis && current && !done && (
          <div className="ecu-transfer-review">
            <div className="ecu-transfer-progress"><span style={{ width: `${((reviewIndex + 1) / analysis.targets.length) * 100}%` }} /></div>
            <div className="ecu-transfer-target-title">
              <div><p className="eyebrow">Ziel-ECU</p><h4>{current.target_hardware.name}</h4><span>Referenz: {current.source_hardware.name}</span></div>
              <strong>{Math.round(current.confidence * 100)} %</strong>
            </div>
            <dl className="ecu-transfer-summary">
              <div><dt>Geprüft</dt><dd>{current.summary.total}</dd></div>
              <div><dt>Neu</dt><dd>{decisionSummary.create}</dd></div>
              <div><dt>Vorhanden</dt><dd>{decisionSummary.reuse}</dd></div>
              <div><dt>Auslassen</dt><dd>{decisionSummary.skip}</dd></div>
              <div><dt>Lernbasis</dt><dd>{analysis.learning.reviewed}</dd></div>
            </dl>
            <div className="ecu-transfer-item-list">
              {current.items.map((item) => {
                const decision = decisionFor(item);
                const isEditing = editingKey === item.plan_key;
                const displayName = decision.action === "reuse"
                  ? item.target_name
                  : decision.recommended_name || item.recommended_name;
                return (
                  <article className={`ecu-transfer-item eng-object-surface ${engineeringObjectTypeClass(item.object_type)} action-${decision.action}`} key={item.plan_key}>
                    <span className={`ecu-transfer-item-type eng-object-badge ${engineeringObjectTypeClass(item.object_type)}`}>{engineeringObjectTypeLabel(item.object_type)}</span>
                    <div className="ecu-transfer-item-copy">
                      <strong>{displayName}</strong>
                      <small>Referenz: {item.source_name}</small>
                      <em>{decision.action === item.suggested_action || (!item.suggested_action && decision.action === item.action) ? item.reason : "Manuell festgelegte Entscheidung"}</em>
                      {isEditing && (
                        <div className="ecu-transfer-item-decision">
                          <span>Behandlung festlegen</span>
                          <div className="ecu-transfer-item-modes" role="group" aria-label={`Behandlung für ${displayName}`}>
                            <button className={decision.action === "create" ? "active" : ""} onClick={() => updateDecision(item, { action: "create", recommended_name: decision.recommended_name || item.recommended_name })} type="button">Neu anlegen</button>
                            {item.target_id && <button className={decision.action === "reuse" ? "active" : ""} onClick={() => updateDecision(item, { action: "reuse", target_id: item.target_id ?? undefined })} type="button">Vorhandenes nutzen</button>}
                            <button className={decision.action === "skip" ? "active" : ""} onClick={() => updateDecision(item, { action: "skip" })} type="button">Auslassen</button>
                          </div>
                          {decision.action === "create" && (
                            <label>
                              <span>Name des neuen Objekts</span>
                              <input onChange={(event) => updateDecision(item, { recommended_name: event.target.value })} value={decision.recommended_name ?? ""} />
                            </label>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="ecu-transfer-item-actions">
                      <span className="ecu-transfer-item-score">
                        {decision.action === "reuse" ? `${Math.round(item.similarity * 100)} % gleich` : decision.action === "skip" ? "auslassen" : "neu anlegen"}
                      </span>
                      <button className="button secondary tiny" onClick={() => setEditingKey(isEditing ? "" : item.plan_key)} type="button">{isEditing ? "Schließen" : "Festlegen"}</button>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        )}

        {done && (
          <div className="ecu-transfer-done">
            <p className="eyebrow">Analyse abgeschlossen</p>
            <h3>{applied} ECU-Strukturen übernommen</h3>
            <dl><div><dt>Neu angelegt</dt><dd>{created}</dd></div><div><dt>Vorhanden genutzt</dt><dd>{reused}</dd></div><div><dt>Ausgelassen</dt><dd>{skipped}</dd></div><div><dt>ECUs abgelehnt</dt><dd>{rejected}</dd></div></dl>
          </div>
        )}

        {error && <div className="inline-error ecu-transfer-error">{error}</div>}
        <footer>
          {!analysis && !done && <><button className="button secondary" disabled={busy} onClick={() => void finish()} type="button">Abbrechen</button><button className="button primary" disabled={busy || !sourceId || !targetIds.length || ecuNodes.length < 2} onClick={() => void analyze()} type="button">{busy ? "KI analysiert …" : `${targetIds.length} ECUs analysieren`}</button></>}
          {analysis && current && !done && <><button className="button danger" disabled={busy} onClick={() => void decide(false)} type="button">Nicht anwenden</button><button className="button primary" disabled={busy || hasInvalidName} onClick={() => void decide(true)} type="button">{busy ? "Wird gespeichert …" : "Entscheidungen anwenden"}</button></>}
          {done && <button className="button primary" onClick={() => void finish()} type="button">Fertig</button>}
        </footer>
      </section>
    </div>
  );
}
