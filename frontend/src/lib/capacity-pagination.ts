export const CAPACITY_PAGE_SIZE = 50;

export function paginateCapacityItems<T>(items: readonly T[], requestedPage: number) {
  const pageCount = Math.max(1, Math.ceil(items.length / CAPACITY_PAGE_SIZE));
  const page = Math.max(0, Math.min(Number.isFinite(requestedPage) ? Math.trunc(requestedPage) : 0, pageCount - 1));
  const start = page * CAPACITY_PAGE_SIZE;
  return {
    items: items.slice(start, start + CAPACITY_PAGE_SIZE),
    page,
    pageCount,
    first: items.length ? start + 1 : 0,
    last: Math.min(start + CAPACITY_PAGE_SIZE, items.length),
    total: items.length,
  };
}
