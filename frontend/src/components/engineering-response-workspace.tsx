"use client";
import { useEffect, useState } from 'react';
import { E2ESequenceDiagram } from './e2e-sequence-diagram';
import type { SequenceDiagramModel } from '@/lib/e2e-sequence';

export function EngineeringResponseWorkspace({ projectId, responseId }: { projectId: string; responseId?: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    const url = responseId ? `/api/engineering/agent/responses/${encodeURIComponent(responseId)}` : '/api/engineering/agent/conversation';
    fetch(url, { headers: {'X-Project-ID':projectId}, cache:'no-store', signal:controller.signal })
      .then(r => r.json()).then(r => { if (!r.success) throw new Error('Die Auswertung konnte nicht geladen werden.'); setData(r.data); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [projectId, responseId]);
  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p role="status">Auswertung wird geladen …</p>;
  if (responseId) {
    const details = (data.metadata as Record<string, unknown> | undefined)?.details as Record<string, unknown> | undefined;
    const sequence = details?.sequence as {status?: string; model?: SequenceDiagramModel} | undefined;
    const model = sequence?.status === 'SIMULATED' && sequence.model?.source === 'SIMULATED'
      && Array.isArray(sequence.model.events) && Array.isArray(sequence.model.transactions)
      && Array.isArray(sequence.model.participants) ? sequence.model : null;
    return <article className="engineering-response-detail"><h2>{String(data.title || 'Ausführliche Auswertung')}</h2>
      <p style={{whiteSpace:'pre-wrap'}}>{String(data.text ?? '')}</p>
      {model && <E2ESequenceDiagram model={model} />}
      <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(details ?? data.findings ?? {}, null, 2)}</pre></article>;
  }
  const answers = Object.values((data.answered_questions ?? {}) as Record<string, {labels?:string[];status?:string}>);
  const decisions = Object.values((data.decisions ?? {}) as Record<string, {status:string;rationale:string}>);
  return <details className="engineering-decision-summary"><summary>Engineering-Entscheidungen ({answers.length + decisions.length})</summary><ul>{answers.map((answer,i) => <li key={i}>{answer.labels?.join(', ')} · {answer.status === 'ANSWERED' ? 'Beantwortet' : 'Übersprungen'}</li>)}{decisions.map((decision,i) => <li key={`decision-${i}`}>{decision.status} · {decision.rationale}</li>)}</ul></details>;
}
