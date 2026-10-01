import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-20260910042736034-d11591d0';
const readRoutes = async () => {
  const response = await fetch('http://127.0.0.1:15050/api/engineering/routing?limit=500', { headers: { 'X-Project-ID': project } });
  assert.ok(response.ok); return (await response.json()).items;
};
const before = await readRoutes(), route = before.find(item => item.route_code === 'RT-17FAA9BD');
assert.ok(route);
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1688, height: 1272 } });
page.setDefaultTimeout(15000);
const errors = [], writes = [], sizes = [];
let failed = false;
page.on('pageerror', error => errors.push(error.message));
await page.route('**/api/engineering/routing**', async handler => {
  if (['GET', 'HEAD'].includes(handler.request().method())) return handler.continue();
  writes.push(handler.request().url()); return handler.abort();
});
const dialog = page.locator('.routing-wizard-dialog');
const body = dialog.locator('.routing-wizard-body');
const steps = dialog.locator('.routing-wizard-steps button');
const next = dialog.getByRole('button', { name: 'Weiter', exact: true });
const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
try {
  await page.goto(`http://127.0.0.1:13500/studio/routing?project=${project}&route=${route.id}`);
  await page.locator('.routing-detail').filter({ hasText: route.route_code }).waitFor();
  const rail = page.locator('.routing-detail-rail'); if (await rail.count()) await rail.click();
  const previousOverflow = await page.evaluate(() => document.body.style.overflow);
  await page.getByRole('button', { name: 'Wizard', exact: true }).click();
  assert.equal(await page.evaluate(() => document.body.style.overflow), 'hidden');
  for (const [width, height] of [[1688, 1272], [1366, 768], [1024, 600], [800, 600], [640, 480], [640, 384], [390, 844]]) {
    await page.setViewportSize({ width, height }); await steps.nth(0).click(); await settle();
    const initial = await dialog.boundingBox(), footer = await dialog.locator(':scope > footer').boundingBox();
    assert.ok(initial.x >= 0 && initial.y >= 0 && initial.x + initial.width <= width + 1 && initial.y + initial.height <= height + 1, `Dialog fits ${width}x${height}`);
    assert.ok(initial.height > height * .9, `Dialog uses available height at ${width}x${height}`);
    const states = [];
    for (let step = 0; step < 7; step++) {
      if (step) { await next.click(); await settle(); }
      const box = await dialog.boundingBox(), currentFooter = await dialog.locator(':scope > footer').boundingBox();
      assert.ok(Math.abs(initial.width - box.width) < 1 && Math.abs(initial.height - box.height) < 1 && Math.abs(footer.y - currentFooter.y) < 1, `Stable geometry on step ${step + 1} at ${width}x${height}`);
      const metrics = await body.evaluate(element => ({ width: element.clientWidth, scrollWidth: element.scrollWidth, height: element.clientHeight, scrollHeight: element.scrollHeight, top: element.scrollTop }));
      assert.ok(metrics.height >= 100, `Readable content area on step ${step + 1} at ${width}x${height}: ${JSON.stringify(metrics)}`);
      assert.ok(metrics.scrollWidth <= metrics.width + 1, `No horizontal clipping on step ${step + 1} at ${width}x${height}: ${JSON.stringify(metrics)}`);
      assert.equal(metrics.top, 0, 'Changing step starts at the top of its content');
      const active = await steps.nth(step).boundingBox(), nav = await dialog.locator('.routing-wizard-steps').boundingBox();
      assert.ok(active.x >= nav.x - 1 && active.x + active.width <= nav.x + nav.width + 1, 'Current step stays visible in narrow navigation');
      const buttonBoxes = await dialog.locator(':scope > footer button').evaluateAll(buttons => buttons.map(button => {
        const rect = button.getBoundingClientRect(); return { text: button.textContent, left: rect.left, right: rect.right, bottom: rect.bottom };
      }));
      assert.ok(buttonBoxes.every(button => button.left >= 0 && button.right <= width + 1 && button.bottom <= height), `Footer reachable: ${JSON.stringify(buttonBoxes)}`);
      if (step === 2) {
        const input = dialog.getByLabel('Benötigte Informationen', { exact: true });
        await input.fill('an, aus und Fehler');
        assert.equal(await input.evaluate(element => getComputedStyle(element).fontSize), '14px');
        if ((width === 1366 && height === 768) || (width === 640 && height === 480)) {
          await page.screenshot({ path: `../backend/runtime/routing-wizard-sizing-${width}x${height}.png` });
        }
        await body.evaluate(element => { element.scrollTop = element.scrollHeight; });
        await dialog.getByRole('region', { name: 'Gewählter Payload' }).scrollIntoViewIfNeeded();
      }
      states.push({ step: step + 1, contentHeight: metrics.height, scrollHeight: metrics.scrollHeight });
    }
    const pageScroll = await page.evaluate(() => window.scrollY);
    await body.evaluate(element => { element.scrollTop = element.scrollHeight; });
    const contentBox = await body.boundingBox();
    await page.mouse.move(contentBox.x + 20, contentBox.y + contentBox.height - 20);
    await page.mouse.wheel(0, 1000); await page.waitForTimeout(150);
    assert.equal(await page.evaluate(() => window.scrollY), pageScroll, 'Scrolling at the boundary does not move the background');
    sizes.push({ width, height, dialog: initial, states });
  }
  await dialog.getByRole('button', { name: 'Dialog schließen' }).click();
  assert.equal(await page.evaluate(() => document.body.style.overflow), previousOverflow);
  assert.deepEqual(errors, []); assert.deepEqual(writes, []); assert.deepEqual(await readRoutes(), before);
  const result = { status: 'passed', sizes, pageErrors: errors, routeWrites: writes.length, liveRoutesUnchanged: true };
  await fs.writeFile('../backend/runtime/routing-wizard-sizing-browser.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} catch (error) {
  failed = true; console.error(error);
  await page.screenshot({ path: '../backend/runtime/routing-wizard-sizing-failure.png' });
} finally {
  const cdp = await page.context().newCDPSession(page);
  await Promise.race([cdp.send('Browser.close').catch(() => {}), new Promise(resolve => setTimeout(resolve, 1500))]);
  process.exit(failed ? 1 : 0);
}
