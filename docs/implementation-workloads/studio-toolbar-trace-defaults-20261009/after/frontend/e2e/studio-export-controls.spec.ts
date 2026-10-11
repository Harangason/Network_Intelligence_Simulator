import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

test('network tools remain grouped and usable at narrow and desktop widths @studio-controls', async ({ page }) => {
  const project = 'nis-e2e-toolbar-' + randomUUID();
  const headers = { 'X-Project-ID': project };
  const created = await page.request.post('/api/engineering/hardware-nodes', {
    headers, data: { name: 'Toolbar Controller', device_type: 'EmbeddedController' },
  });
  expect(created.ok(), await created.text()).toBe(true);
  const controller = await created.json();
  const view = await (await page.request.get('/api/engineering/workflow/topology', { headers })).json();
  const saved = await page.request.put('/api/engineering/workflow/topology', {
    headers, data: { expected_token: view.edit_token, topology: {
      nodes: [{ id: controller.id, engineeringId: controller.id, name: controller.name,
        kind: 'ecu', x: 100, y: 100, width: 210, height: 150, ports: [] }], edges: [],
    } },
  });
  expect(saved.ok(), await saved.text()).toBe(true);
  await page.goto(`/studio?mode=network&project=${project}`);
  await expect(page.getByRole('heading', { name: 'ECU-Netzwerk', exact: true })).toBeVisible();
  for (const width of [954, 390, 1417]) {
    await page.setViewportSize({ width, height: 1244 });
    const toolbar = page.locator('.net-toolbar');
    for (const name of ['Geräte hinzufügen', 'Netzwerkansicht', 'Auswahl bearbeiten']) {
      await expect(toolbar.getByRole('group', { name, exact: true })).toBeVisible();
    }
    expect(await toolbar.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
    const overflow = await toolbar.evaluate(element => {
      const bounds = element.getBoundingClientRect();
      return [...element.querySelectorAll('button, input')].filter(control => {
        const rect = control.getBoundingClientRect();
        return rect.width > 0 && (rect.left < bounds.left - 1 || rect.right > bounds.right + 1);
      }).map(control => control.textContent);
    });
    expect(overflow).toEqual([]);
    await toolbar.getByRole('button', { name: 'Vergrößern', exact: true }).click();
    await expect(toolbar.getByRole('button', { name: 'Zoom auf 100 Prozent zurücksetzen' })).not.toHaveText('100 %');
    await toolbar.getByRole('button', { name: 'Zoom auf 100 Prozent zurücksetzen' }).click();
    await expect(toolbar.getByRole('button', { name: 'Zoom auf 100 Prozent zurücksetzen' })).toHaveText('100 %');
    await toolbar.getByRole('button', { name: '+ ECU', exact: true }).click();
    await expect(page.getByRole('menu', { name: 'ECU auswählen' })).toBeVisible();
    await toolbar.getByRole('button', { name: '+ ECU', exact: true }).click();
  }
});

for (const scenario of [
  { name: 'CAN', technologies: ['CAN_FD'], expected: ['BLF', 'DBC'] },
  { name: 'Ethernet', technologies: ['ETHERNET'], expected: ['PCAP'] },
  { name: 'mixed', technologies: ['CAN_FD', 'ETHERNET', 'LIN'], expected: ['BLF', 'DBC', 'PCAP'] },
]) test(`simulation selects real native defaults for ${scenario.name} and preserves manual choice @studio-controls`, async ({ page }) => {
  const project = 'nis-e2e-formats-' + randomUUID();
  const headers = { 'X-Project-ID': project };
  const initial = await (await page.request.get('/api/engineering/workflow/parameters', { headers })).json();
  const parameters = { industry: 'custom', technology: scenario.technologies[0].toLowerCase(),
    networks: scenario.technologies.map((technology, index) => ({ id: `bus-${index}`, name: `Bus ${index}`, technology })) };
  const saved = await page.request.patch('/api/engineering/workflow/parameters', {
    headers, data: { expected_token: initial.edit_token, parameters },
  });
  expect(saved.ok(), await saved.text()).toBe(true);
  await page.goto(`/studio/simulation?project=${project}`);
  const trigger = page.locator('.trace-format-trigger');
  await expect(trigger).toContainText(scenario.expected.join(', '));
  await expect(trigger.locator('strong')).toHaveText(String(scenario.expected.length));
  await trigger.click();
  const picker = page.getByRole('dialog', { name: 'Trace-Formate auswählen' });
  await expect(picker).toBeVisible();
  await expect(picker.getByRole('checkbox', { name: 'Universelle Tabellenablage', exact: false })).not.toBeChecked();
  const csv = picker.getByRole('checkbox', { name: 'Universelle Tabellenablage', exact: false });
  await csv.check();
  await page.evaluate(() => window.dispatchEvent(new Event('workflow:changed')));
  await expect(csv).toBeChecked();
  await expect(trigger.locator('strong')).toHaveText(String(scenario.expected.length + 1));
});
