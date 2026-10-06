import {expect, test} from 'playwright/test';

test('source directory search sort short links and publication notice retain project @small', async ({page}) => {
  const project = 'source-directory-' + Date.now();
  await page.goto('/?project=' + project);
  await page.getByRole('navigation', {name: 'Hauptnavigation'}).getByRole('link', {name: 'Quellen', exact: true}).click();
  await expect(page).toHaveURL(new RegExp('/sources\\?project=' + project));
  await expect(page.getByRole('heading', {name: 'Quellenverzeichnis', exact: true})).toBeVisible();
  const table = page.getByRole('table').first();
  await expect(table.locator(':scope > tbody > tr')).toHaveCount(50);
  await page.getByRole('button', {name: /Name Bustyp/}).click();
  await expect(table.locator('th[aria-sort="ascending"]')).toContainText('Name Bustyp');
  await page.getByRole('button', {name: /Name Bustyp/}).click();
  await expect(table.locator('th[aria-sort="descending"]')).toContainText('Name Bustyp');
  await page.getByLabel('Fuzzy-Suche').fill('ethernt');
  await expect(table.locator(':scope > tbody > tr').first()).toBeVisible();
  await expect(table.locator(':scope > tbody')).toContainText('ETHERNET');
  await page.getByLabel('Fuzzy-Suche').fill('Matter 1.6.1');
  await expect(table.locator(':scope > tbody > tr')).toHaveCount(1);
  await table.getByText('1 Quelle anzeigen', {exact: true}).click();
  await expect(table.getByRole('link').first()).toHaveText('Quelle öffnen ↗');
  await table.getByRole('button', {name: /Lizenzhinweis/}).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('keine öffentliche Veröffentlichung');
  await expect(dialog.getByRole('link', {name: 'Originalquelle öffnen ↗'})).toHaveAttribute('href', /csa-iot.org/);
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await page.getByLabel('Fuzzy-Suche').fill('zzzzzz');
  await expect(page.getByText('Keine passenden Quellen.', {exact: false})).toBeVisible();
});

test('license references stay pending and locked; technology remains selectable @small', async ({page}) => {
  const project = 'source-license-' + Date.now();
  await page.goto('/sources?project=' + project);
  await page.getByRole('heading', {name: 'Projektbezogene Technikfreigaben'}).waitFor();
  await page.locator('article').filter({hasText: 'NMEA2000'}).getByRole('button', {name: 'Nachweise & Freigabe'}).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Lizenzgeber').fill('Synthetic test issuer');
  await dialog.getByLabel('Lizenz- / Vertragsreferenz').fill('Isolated test reference, not a real license');
  await dialog.getByLabel('Erlaubter Nutzungsumfang').fill('Synthetic request for NIS testing');
  await dialog.getByRole('button', {name: 'Nachweis einreichen'}).click();
  await expect(dialog).toContainText('Die Technik bleibt bis zur Betreiberprüfung gesperrt.');
  await expect(dialog).toContainText('PENDING');
  await page.keyboard.press('Escape');
  const switched = page.waitForResponse(response => response.url().endsWith('/api/technology-sources') && response.request().headers()['x-project-id'] === project + '-other');
  await page.evaluate(nextProject => history.pushState(null, '', '/sources?project_id=' + nextProject), project + '-other');
  await switched;
  await page.locator('article').filter({hasText: 'NMEA2000'}).getByRole('button', {name: 'Nachweise & Freigabe'}).click();
  await expect(dialog).not.toContainText('Isolated test reference');
  await page.keyboard.press('Escape');
  await page.goto('/studio?mode=parameters&project=' + project);
  await page.getByLabel('Anwendungsbereich auswählen').selectOption('custom');
  const initial = page.locator('#initial-technology');
  await expect(initial.locator('option[value="nmea2000"]')).toHaveCount(1);
  await initial.selectOption('nmea2000');
  const technology = page.locator('#technology');
  await expect(technology.locator('option[value="nmea2000"]')).toHaveCount(1);
  await technology.selectOption('nmea2000');
  await expect(technology).toHaveValue('nmea2000');
  await expect(page.getByText('⚠ Ausführung gesperrt: Eine geprüfte projektbezogene Technikfreigabe fehlt.')).toBeVisible();
  const response = await page.request.post('/api/technology-licenses', {headers: {'X-Project-ID': project},
    data: {technology: 'nmea2000', issuer: 'Fixture', reference: 'Fixture', scope_description: 'Fixture', status: 'APPROVED'}});
  expect(response.status()).toBe(400);
});

test('source directory is readable in both themes and reachable on a narrow viewport @small', async ({page}) => {
  await page.goto('/sources?project=source-visual-' + Date.now());
  const heading = page.getByRole('heading', {name: 'Quellenverzeichnis', exact: true});
  await heading.waitFor();
  for (const theme of ['Hell', 'Dunkel']) {
    await page.getByRole('button', {name: theme, exact: true}).click();
    const ratio = await heading.evaluate(element => {
      const foreground = getComputedStyle(element).color.match(/[\d.]+/g)!.slice(0, 3).map(Number);
      const backgroundHex = getComputedStyle(document.documentElement).getPropertyValue('--background').trim();
      const background = [1, 3, 5].map(index => parseInt(backgroundHex.slice(index, index + 2), 16));
      const luminance = (color: number[]) => color.map(value => value / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
        .reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
      const a = luminance(foreground), b = luminance(background);
      return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    });
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  }
  await page.setViewportSize({width: 600, height: 950});
  await expect(page.getByRole('navigation', {name: 'Hauptnavigation'}).getByRole('link', {name: 'Quellen', exact: true})).toBeVisible();
  await expect(heading).toBeVisible();
});


test('five 5G sources are collected beneath one collapsed technology entry @small', async ({page}) => {
  await page.goto('/sources?project=source-groups-' + Date.now());
  const table = page.getByRole('table').first();
  const group = table.locator(':scope > tbody > tr[data-technology="5g"]');
  await expect(group).toHaveCount(1);
  await expect(group.locator('details')).not.toHaveAttribute('open', '');
  await group.getByText('5 Quellen anzeigen', {exact: true}).click();
  await expect(group.getByRole('link', {name: /Quelle öffnen:/})).toHaveCount(5);
  await expect(group.getByRole('button', {name: /Lizenzhinweis:/})).toHaveCount(5);
  await group.getByRole('button', {name: /Lizenzhinweis:/}).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await group.locator('summary').click();
  await expect(group.getByRole('link').first()).not.toBeVisible();
});
