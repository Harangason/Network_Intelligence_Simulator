import assert from "node:assert/strict";
import test from "node:test";
import { CAPACITY_PAGE_SIZE, paginateCapacityItems } from "./capacity-pagination.ts";

test("capacity lists contain at most 50 entries with no losses or duplicates", () => {
  assert.equal(CAPACITY_PAGE_SIZE, 50);
  for (const count of [0, 1, 49, 50, 51, 100, 249, 250, 251, 1000]) {
    const items = Array.from({ length: count }, (_, id) => ({ id }));
    const { pageCount } = paginateCapacityItems(items, 0);
    const collected = [];
    for (let page = 0; page < pageCount; page++) {
      const result = paginateCapacityItems(items, page);
      assert.ok(result.items.length <= 50);
      assert.equal(result.page, page);
      assert.equal(result.total, count);
      assert.equal(result.first, count ? page * 50 + 1 : 0);
      assert.equal(result.last, Math.min((page + 1) * 50, count));
      collected.push(...result.items);
    }
    assert.deepEqual(collected, items);
  }
});

test("an invalid or removed page is clamped to available results", () => {
  const items = Array.from({ length: 51 }, (_, id) => id);
  assert.equal(paginateCapacityItems(items, -1).page, 0);
  assert.equal(paginateCapacityItems(items, 100).page, 1);
  assert.equal(paginateCapacityItems(items, Number.NaN).page, 0);
  assert.equal(paginateCapacityItems(items, Number.POSITIVE_INFINITY).page, 0);
  assert.deepEqual(paginateCapacityItems(items.slice(0, 20), 4).items, items.slice(0, 20));
  assert.deepEqual(paginateCapacityItems([], 4), { items: [], page: 0, pageCount: 1, first: 0, last: 0, total: 0 });
});

test("background snapshots retain the page and use the new values", () => {
  const before = Array.from({ length: 250 }, (_, id) => ({ id, load: 10 }));
  const after = before.map((item) => ({ ...item, load: 20 }));
  const first = paginateCapacityItems(before, 3);
  const next = paginateCapacityItems(after, first.page);
  assert.equal(next.page, 3);
  assert.deepEqual(next.items.map((item) => item.id), first.items.map((item) => item.id));
  assert.ok(next.items.every((item) => item.load === 20));
});

test("sorting precedes pagination without mutating the input", () => {
  const source = Array.from({ length: 101 }, (_, id) => id);
  const sorted = [...source].sort((left, right) => right - left);
  assert.deepEqual(paginateCapacityItems(sorted, 0).items, sorted.slice(0, 50));
  assert.deepEqual(paginateCapacityItems(sorted, 1).items, sorted.slice(50, 100));
  assert.deepEqual(paginateCapacityItems(sorted, 2).items, [0]);
  assert.equal(source[0], 0);
});
