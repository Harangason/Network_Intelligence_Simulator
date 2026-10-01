import { chromium } from '../../frontend/node_modules/playwright/index.mjs';

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const response = await page.goto('http://127.0.0.1:13500/studio?mode=parameters&project=20260930082857843-09a6b82a');
  await page.locator('#bitrate').waitFor({ timeout: 20000 });
  const result = await page.evaluate(() => {
    const clock = document.querySelector('#bitrate');
    const physical = document.querySelector('.parameter-group-physical');
    return {
      domain: document.querySelector('#domain')?.value,
      technology: document.querySelector('#technology')?.value,
      clock: clock?.value,
      clock_required: clock?.required,
      clock_valid: clock?.checkValidity(),
      mode_limits_visible: physical?.textContent?.includes('Standard ≤ 100.000 bit/s')
        && physical?.textContent?.includes('Fast ≤ 400.000 bit/s')
        && physical?.textContent?.includes('High Speed ≤ 3.400.000 bit/s'),
      source_link: physical?.querySelector('a[href*="UM10204.pdf"]')?.href,
    };
  });
  result.http_status = response?.status();
  console.log(JSON.stringify(result));
  if (result.http_status !== 200 || result.domain !== 'custom' || result.technology !== 'i2c'
    || result.clock !== '' || result.clock_required !== true || result.clock_valid !== false
    || result.mode_limits_visible !== true || !result.source_link) process.exitCode = 1;
} finally {
  await browser.close();
}
