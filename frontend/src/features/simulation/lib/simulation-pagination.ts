/** Bound rendering work without dropping access to later trace items. */
export function simulationPage<T>(items: readonly T[], requestedPage: number, pageSize: number) {
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const page = Math.max(0, Math.min(Number.isFinite(requestedPage) ? Math.trunc(requestedPage) : 0, pageCount - 1));
  const start = page * pageSize;
  return { items: items.slice(start, start + pageSize), page, pageCount, start,
    first: items.length ? start + 1 : 0, last: Math.min(start + pageSize, items.length), total: items.length };
}
