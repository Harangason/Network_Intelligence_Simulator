/**
 * DE: Prüft ausschließlich den generierten Dateikatalog im isolierten Browser.
 * EN: Verifies only the generated file catalog in an isolated browser.
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const { chromium } = require(path.resolve(__dirname, '../../../frontend/node_modules/playwright'));

(async () => {
  const inventory = JSON.parse(fs.readFileSync(path.join(__dirname, 'inventory.json'), 'utf8'));
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.join(__dirname, 'index.html')).href);
    const total = await page.locator('tbody tr').count();
    assert.equal(total, inventory.files.length);
    assert.equal(await page.locator('tbody tr:visible').count(), total);
    await page.locator('#search').fill('TechnologyRegistry');
    assert(await page.locator('tbody tr:visible').count() > 0);
    assert(await page.locator('tbody tr:visible').filter({ hasText: 'backend/communication/technologies/core/registry.py' }).count() > 0);
    await page.screenshot({ path: path.join(__dirname, 'preview.png'), fullPage: false });
    await page.locator('#search').fill('');
    await page.locator('#kind').selectOption('Tests');
    const testCount = inventory.files.filter(file => file.category === 'Tests').length;
    assert.equal(await page.locator('tbody tr:visible').count(), testCount);
    await page.locator('#search').fill('einen_nicht_vorhandenen_dateinamen_987654321');
    assert.equal(await page.locator('tbody tr:visible').count(), 0);
    await page.locator('#search').fill('');
    await page.locator('#kind').selectOption('');
    assert.equal(await page.locator('tbody tr:visible').count(), total);
    const linkErrors = [];
    for (const file of inventory.files) {
      assert(file.description && file.evidence, file.path);
      if (!fs.existsSync(path.resolve(inventory.root, file.path))) linkErrors.push(file.path);
    }
    assert.deepEqual(linkErrors, []);
    assert.deepEqual(errors, []);
    assert.equal(new Set(inventory.files.map(file => file.path)).size, total);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('#search').fill('workflow-api.ts');
    assert(await page.locator('tbody tr:visible').count() > 0);
    const verification = {
      status: 'PASS', artifact_scope: 'Offline-Dateikatalog; keine NIS-Anwendungs-/Workflowprüfung',
      files: total, tests_filter_matches: testCount, browser_errors: errors,
      checks: ['HTML-Zeilenzahl entspricht Inventar', 'Initiale Anzeige', 'Symbolsuche', 'Kategoriefilter', 'Leere Trefferliste', 'Filter zurücksetzen', 'Quellenpfade vorhanden', 'Beschreibungen vorhanden', 'Keine doppelten Pfade', 'Keine Browser-JavaScriptfehler', 'Suche bei mobiler Breite'],
      verified_at: new Date().toISOString(),
    };
    fs.writeFileSync(path.join(__dirname, 'verification.json'), JSON.stringify(verification, null, 2) + '\n');
    console.log(JSON.stringify(verification));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
