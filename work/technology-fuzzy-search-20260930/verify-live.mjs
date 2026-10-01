import { chromium } from '../../frontend/node_modules/playwright/index.mjs';

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1424, height: 1244 } });
  const url = 'http://127.0.0.1:13500/studio?mode=parameters&project=20260930082857843-09a6b82a';
  const response = await page.goto(url, { waitUntil: 'domcontentloaded' });
  const bus = page.locator('#technology');
  await bus.waitFor({ timeout: 20000 });
  const search = page.getByRole('searchbox', { name: 'Bus / Protokoll suchen' });
  await search.waitFor();
  const original = await bus.inputValue();
  const fullCount = await bus.locator('option').count();
  const selectBox = await bus.boundingBox();
  const searchBox = await search.boundingBox();
  await search.fill('profnet');
  await page.waitForTimeout(150);
  const found = await bus.locator('option[value="profinet"]').count();
  const preserved = await bus.inputValue();
  await search.clear();
  await page.waitForTimeout(150);
  const restoredCount = await bus.locator('option').count();
  const result = {
    status: response?.status(),
    selected_before: original,
    selected_after_search: preserved,
    full_count: fullCount,
    restored_count: restoredCount,
    profinet_matches: found,
    adjacent: Boolean(selectBox && searchBox && searchBox.x >= selectBox.x + selectBox.width - 1),
  };
  console.log(JSON.stringify(result));
  if (result.status !== 200 || result.selected_before !== 'i2c' || result.selected_after_search !== 'i2c'
    || result.full_count !== 125 || result.restored_count !== 125 || result.profinet_matches !== 1
    || !result.adjacent) process.exitCode = 1;
} finally {
  await browser.close();
}
