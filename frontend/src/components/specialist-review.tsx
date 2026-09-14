"use client";

export type SpecialistReviewResult = {
  status: 'REVIEWED' | 'REVIEWING' | 'UNAVAILABLE' | 'NO_CANDIDATES';
  total?: number;
  model: string | null;
  trace_id: string;
  decisions: { id: string; recommended: boolean; reason: string }[];
  gaps: string[];
};

export function SpecialistReview({ review }: { review?: SpecialistReviewResult }) {
  if (!review) return null;
  return <section aria-label="Bewertung des Fachagenten">
    <strong>{review.status === 'REVIEWING' ? `Fachagent prüft · ${review.decisions.length} von ${review.total}` : review.status === 'REVIEWED' ? `Fachagent · ${review.model}` : review.status === 'NO_CANDIDATES' ? 'Keine Kandidaten zur KI-Prüfung' : 'Fachagent nicht verfügbar'}</strong>
    {review.gaps.map((gap, index) => <p role="status" key={index}>{gap}</p>)}
    {!!review.decisions.length && <details><summary>{review.decisions.length} geprüfte Vorschläge</summary><ul>
      {review.decisions.map(item => <li key={item.id}><strong>{item.recommended ? 'Empfohlen' : 'Klärung erforderlich'}</strong> · {item.reason}</li>)}
    </ul></details>}
  </section>;
}
