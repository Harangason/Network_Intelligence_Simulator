/** Preserve the shared job/focus when changing a trace-analysis projection. */
export function traceViewHref(search: string, view: string): string {
  const query = new URLSearchParams(search);
  query.set('view', view);
  return `/trace-analysis?${query.toString()}`;
}
