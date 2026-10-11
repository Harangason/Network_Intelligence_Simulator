"use client";

import { useEffect, useMemo, useState } from 'react';
import { engineeringContextHref } from '@/features/agent/lib/assistant-context';
import { getCatalog } from '@/shared/api/api';
import { getWorkflowParameters, saveWorkflowParameters } from '@/features/workflow/lib/workflow-api';
import { compactProjectId, withProjectParam } from '@/features/settings/lib/user-settings';
import type { Technology, TechnologyParameterField } from '@/shared/api/types';
import { confirmNetworkParameters, groupPreflightFindings, technologyKey, technologyParameterValues, type DeclaredNetwork, type ReviewFinding } from '@/features/communication/lib/technology-parameters';
import { notifyWorkflowChanged } from '../../workflow/ui/workflow-header';

type Snapshot = Awaited<ReturnType<typeof getWorkflowParameters>>;
const rateFields = (technology: Technology) => (technology.parameter_schema ?? []).filter(field => field.scope === 'network' && field.unit === 'bit/s');

export function NetworkRateReview({ technology, networks, snapshot, projectId, disabled, onContinue, fieldKeys, onBusyChange }: {
  technology: Technology; networks: DeclaredNetwork[]; snapshot: Snapshot; projectId: string; disabled: boolean; onContinue: () => Promise<void>; fieldKeys?: string[]; onBusyChange?: (busy: boolean) => void;
}) {
  const [selected, setSelected] = useState(networks.map(item => item.id));
  const fields = rateFields(technology).filter(field => !fieldKeys?.length || fieldKeys.includes(field.key));
  const proposed = technologyParameterValues(snapshot.parameters, technology);
  const [values, setValues] = useState<Record<string, unknown>>(() => Object.fromEntries(fields.map(field => {
    const common = networks.map(item => item[field.key]);
    return [field.key, common.every(value => value !== undefined && value !== null && value !== '' && value === common[0]) ? common[0] : proposed[field.key] ?? ''];
  })));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function confirm() {
    if (busy || disabled || !snapshot.edit_token) return;
    setBusy(true); onBusyChange?.(true); setError('');
    try {
      const parameters = confirmNetworkParameters(snapshot.parameters, technology, selected, values);
      const saved = await saveWorkflowParameters(parameters, snapshot.edit_token, projectId);
      if (saved.project_id !== snapshot.project_id) throw new Error('Die Bestätigung gehört zu einem anderen Projekt.');
      notifyWorkflowChanged();
      await onContinue();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Die Parameter konnten nicht bestätigt werden.'); }
    finally { setBusy(false); onBusyChange?.(false); }
  }
  if (!fields.length) return null;
  return <form className="agent-wizard-inline-question" aria-label={`${technology.label ?? technology.id.toUpperCase()}-Netze bestätigen`} onSubmit={event => { event.preventDefault(); void confirm(); }}>
    <strong>{technology.label ?? technology.id.toUpperCase()} · {networks.length} betroffene Netze</strong>
    <p>Die Rate fehlt als bestätigter Projektwert. Kapazität und Timing sind davon abhängige Befunde. Ein Profilvorschlag wird erst mit deiner Bestätigung für die ausgewählten Netze verwendet.</p>
    <fieldset disabled={disabled || busy}>
      {fields.map((field: TechnologyParameterField) => <label className="field parameter-field-finding" key={field.key}>
        <span>{field.label} ({field.unit})</span>
        <input aria-label={`${field.label} · betroffene Netze`} name={field.key} required type="number" min={field.min} max={field.max} step="any" value={String(values[field.key] ?? '')}
          onChange={event => setValues(current => ({ ...current, [field.key]: event.target.value === '' ? '' : Number(event.target.value) }))} />
        <small>{field.default === undefined && field.simulation_default !== undefined
          ? 'SIMULATIONSANNAHME · Kein Gerätenachweis · vor der Bestätigung Hardware und physische Rate prüfen'
          : 'Profilvorschlag · vor der Übernahme Hardware und physische Rate prüfen'}</small>
      </label>)}
      <details><summary>Netze auswählen ({selected.length}/{networks.length})</summary>
        {networks.map(network => <label key={network.id}><input type="checkbox" checked={selected.includes(network.id)} onChange={event => setSelected(current => event.target.checked ? [...current, network.id] : current.filter(id => id !== network.id))} />{network.name ?? network.id}</label>)}
      </details>
      <button className="button primary tiny" type="submit" disabled={!selected.length || !fields.length || !snapshot.edit_token}>
        {busy ? 'Parameter werden bestätigt …' : `Für ${selected.length} Netze bestätigen & erneut prüfen`}
      </button>
    </fieldset>
    {error && <p className="notice error" role="alert">{error} Bei einem geänderten Projektstand bitte die Rückfragen neu laden.</p>}
  </form>;
}

export function WizardPreflightReview({ findings, projectId, disabled = false, onContinue }: {
  findings: ReviewFinding[]; projectId: string; disabled?: boolean; onContinue: () => Promise<void>;
}) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [technologies, setTechnologies] = useState<Technology[]>([]);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const groups = useMemo(() => groupPreflightFindings(findings), [findings]);
  const signature = groups.map(group => group.id).join('|');
  useEffect(() => {
    let active = true; setSnapshot(null); setError('');
    void Promise.all([getWorkflowParameters(projectId), getCatalog({ strict: true })]).then(([state, catalog]) => {
      if (!active) return;
      if (compactProjectId(state.project_id) !== compactProjectId(projectId)) throw new Error('Die Rückfragen gehören zu einem anderen Projekt.');
      setTechnologies(catalog.domains.flatMap(domain => domain.technologies)); setSnapshot(state);
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Rückfragen konnten nicht geladen werden.'); });
    return () => { active = false; };
  }, [projectId, signature, reload]);
  const networks = (Array.isArray(snapshot?.parameters.networks) ? snapshot!.parameters.networks : []) as DeclaredNetwork[];
  const rateGroups = new Map<string, DeclaredNetwork[]>();
  const handled = new Set<string>();
  for (const group of groups) {
    const network = group.objectType === 'Network' && group.rateMissing ? networks.find(item => item.id === group.objectId) : undefined;
    const technology = network ? technologies.find(item => item.id === technologyKey(network.technology)) : undefined;
    if (network && technology && rateFields(technology).length) {
      rateGroups.set(technology.id, [...(rateGroups.get(technology.id) ?? []), network]); handled.add(group.id);
    }
  }
  return <section aria-label="Blockierende Preflight-Befunde">
    <strong>Vor der Simulation zu klären · {groups.length} betroffene Objekte</strong>
    {!snapshot && !error && <p role="status">Betroffene Netze und Technologieprofile werden geladen …</p>}
    {[...rateGroups.entries()].map(([id, items]) => <NetworkRateReview key={`${snapshot!.edit_token}:${id}`} technology={technologies.find(item => item.id === id)!}
      networks={items} snapshot={snapshot!} projectId={projectId} disabled={disabled} onContinue={onContinue} />)}
    {groups.filter(group => !handled.has(group.id)).map(group => <article key={group.id}>
      <strong>{networks.find(item => item.id === group.objectId)?.name ?? group.objectId ?? 'Projektangaben'}</strong>
      <p>{group.findings[0]?.recommendation ?? group.findings[0]?.message ?? 'Nachweis ergänzen und erneut prüfen.'}</p>
      <a className="button secondary tiny" href={engineeringContextHref({ object_type: group.objectType, id: group.objectId ?? '' }, projectId) ?? withProjectParam('/studio?mode=parameters', projectId)}>Betroffene Angaben bearbeiten</a>
      <details><summary>{group.findings.length} zusammenhängende Befunde</summary><ul>{group.findings.map((finding, index) => <li key={index}><strong>{finding.code}</strong>: {finding.message}</li>)}</ul></details>
    </article>)}
    <details><summary>Alle technischen Befunde ({findings.length})</summary><ul>{findings.map((finding, index) => <li key={index}>{finding.code}: {finding.message}</li>)}</ul></details>
    <button className="button secondary tiny" type="button" disabled={disabled} onClick={() => setReload(value => value + 1)}>Rückfragen neu laden</button>
    {error && <p role="alert">{error}</p>}
  </section>;
}
