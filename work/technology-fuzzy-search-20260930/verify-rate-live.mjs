import { chromium } from '../../frontend/node_modules/playwright/index.mjs';

const project = '20260930082857843-09a6b82a';
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const url = `http://127.0.0.1:13500/studio?mode=parameters&project=${project}`;
  const response = await page.goto(url, { waitUntil: 'domcontentloaded' });
  const clock = page.locator('input[name="bitrate"]');
  await clock.waitFor({ timeout: 20000 });
  const before = await page.request.get('http://127.0.0.1:13500/api/engineering/workflow/parameters', {
    headers: { 'X-Project-ID': project },
  });
  const parameters = (await before.json()).parameters;
  const result = {
    http_status: response?.status(),
    technology: await page.locator('#technology').inputValue(),
    clock: await clock.inputValue(),
    proposal_visible: await page.getByText('UNVERIFIED · Profilvorschlag').first().isVisible(),
    saved_clock: parameters.technology_parameters?.i2c?.values?.bitrate ?? null,
  };
  console.log(JSON.stringify(result));
  if (result.http_status !== 200 || result.technology !== 'i2c' || result.clock !== '100000'
    || !result.proposal_visible || result.saved_clock !== null) process.exitCode = 1;
} finally {
  await browser.close();
}
