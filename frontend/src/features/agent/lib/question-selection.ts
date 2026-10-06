/** Polling an open question must not discard an answer being edited. */
export function reconcileQuestionSelection(local: string[], status: string, saved: string[] | undefined, edited: boolean): string[] {
  if (status === 'OPEN' && (edited || !saved?.length)) return local;
  return saved ?? local;
}
