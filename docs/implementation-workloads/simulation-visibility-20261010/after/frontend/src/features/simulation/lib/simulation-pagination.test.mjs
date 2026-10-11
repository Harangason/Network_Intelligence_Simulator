import assert from 'node:assert/strict';
import test from 'node:test';
import { simulationPage } from './simulation-pagination.ts';

for (const [count, size] of [[1404, 60], [10000, 200]]) {
  test(`all ${count} trace items remain reachable without duplication across bounded pages`, () => {
    const items = Array.from({ length: count }, (_, id) => ({ id }));
    const collected = [];
    for (let page = 0; page < Math.ceil(count / size); page++) {
      const result = simulationPage(items, page, size);
      assert.ok(result.items.length <= size);
      assert.equal(result.first, page * size + 1);
      assert.equal(result.last, Math.min((page + 1) * size, count));
      collected.push(...result.items);
    }
    assert.deepEqual(collected, items);
  });
}
test('filter shrink, empty data and invalid pages cannot leave a blank unreachable page', () => {
  assert.equal(simulationPage([1, 2], 80, 60).page, 0);
  assert.deepEqual(simulationPage([], 80, 60), { items: [], page: 0, pageCount: 1, start: 0, first: 0, last: 0, total: 0 });
  for (const page of [-3, NaN, Infinity]) assert.equal(simulationPage([1], page, 60).page, 0);
});
