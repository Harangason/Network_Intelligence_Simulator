import { chromium } from '../../frontend/node_modules/playwright/index.mjs';

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const workflowCalls = [];
  page.on('response', response => {
    if (response.url().includes('/api/engineering/workflow')) workflowCalls.push({ status: response.status(), url: response.url(), project: response.request().headers()['x-project-id'] });
  });
  page.on('requestfailed', request => {
    if (request.url().includes('/api/engineering/workflow')) workflowCalls.push({ failed: request.failure()?.errorText, url: request.url(), project: request.headers()['x-project-id'] });
  });
  const url = 'http://127.0.0.1:13500/studio?mode=parameters&project=20260930082857843-09a6b82a';
  const response = await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.locator('#technology').waitFor({ timeout: 15000 }).catch(async error => {
    console.log(JSON.stringify({ page_status: response?.status(), url: page.url(), workflowCalls, text: (await page.locator('body').innerText()).slice(0, 1200) }));
    throw error;
  });
  const result = {
    http_status: response?.status(),
    domain: await page.locator('#domain').inputValue(),
    technology: await page.locator('#technology').inputValue(),
    technology_options: await page.locator('#technology option').count(),
    i2c_visible: await page.locator('#technology option[value="i2c"]').count() === 1,
    profinet_visible: await page.locator('#technology option[value="profinet"]').count() === 1,
  };
  console.log(JSON.stringify(result));
  if (result.http_status !== 200 || result.domain !== 'custom' || result.technology !== 'i2c'
    || result.technology_options !== 125 || !result.i2c_visible || !result.profinet_visible) process.exitCode = 1;
} finally {
  await browser.close();
}
