import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

// Normal modelling APIs prepare a separate project. This is CRUD/UI coverage;
// wizard.spec.ts independently proves generated models and all nine stages.
test('message and signal routing permission survives save, reload and parent override @routing-permission', async ({ page }, info) => {
  const project = 'nis-e2e-routing-permission-' + randomUUID();
  const headers = { 'X-Project-ID': project };
  async function create(resource: string, data: Record<string, unknown>) {
    const response = await page.request.post(`/api/engineering/${resource}`, { headers, data });
    expect(response.ok(), await response.text()).toBe(true);
    return response.json();
  }
  async function read(resource: string, id: string) {
    const response = await page.request.get(`/api/engineering/${resource}/${id}`, { headers });
    expect(response.ok()).toBe(true);
    return response.json();
  }
  const sensor = await create('hardware-nodes', { name: 'Hallgeber', device_type: 'SensorController' });
  const controller = await create('hardware-nodes', { name: 'Motorsteuerung', device_type: 'ECU' });
  const iface = await create('interfaces', { name: 'MotorMessung', hardware_node_id: sensor.id, interface_type: 'LIN' });
  const message = await create('messages', {
    name: 'MotorMessung', interface_id: iface.id, message_id_hex: '0x12', direction: 'tx', cycle_ms: 100, dlc: 2,
    configuration: { communication_contract: { scope: 'LOCAL_IO', role: 'MEASUREMENT', consumer_refs: [controller.id] } },
  });
  const signal = await create('signals', {
    name: 'HallPosition', message_id: message.id, start_bit: 0, length_bits: 16,
    byte_order: 'little_endian', data_type: 'unsigned', factor: 1, offset_value: 0,
    configuration: { routing: { source: 'manual' } },
  });
  async function open(resource: string, id: string) {
    await page.goto(`/studio/engineering?project=${project}&resource=${resource}&object=${id}&edit=1`);
    await expect(page.getByRole('switch', { name: 'Geroutet', exact: true })).toBeVisible();
  }
  async function save(resource: string, id: string) {
    const saved = page.waitForResponse(response => response.url().endsWith(`/api/engineering/${resource}/${id}`) && response.request().method() === 'PATCH');
    await page.getByRole('button', { name: 'Änderungen speichern', exact: true }).click();
    expect((await saved).ok()).toBe(true);
  }
  await page.setViewportSize({ width: 768, height: 900 });
  await open('signals', signal.id);
  const toggle = page.getByRole('switch', { name: 'Geroutet', exact: true });
  await expect(toggle).toBeChecked();
  await toggle.click();
  await expect(toggle).not.toBeChecked();
  const size = await toggle.boundingBox();
  expect(size!.width).toBeGreaterThan(90);
  expect(size!.height).toBeLessThan(70);
  const permissionPanel = page.locator('.eng-routing-permission');
  const panelSize = await permissionPanel.boundingBox();
  expect(panelSize!.width).toBeLessThanOrEqual(768);
  expect(await permissionPanel.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  await save('signals', signal.id);
  const storedSignal = await read('signals', signal.id);
  expect(storedSignal.configuration.routing).toEqual({ source: 'manual', enabled: false });
  expect([storedSignal.start_bit, storedSignal.length_bits]).toEqual([0, 16]);
  expect((await read('messages', message.id)).dlc).toBe(2);
  await open('signals', signal.id);
  await expect(toggle).not.toBeChecked();
  // The parent can restrict a signal without rewriting the child's own choice.
  await toggle.click();
  await save('signals', signal.id);
  await open('messages', message.id);
  await toggle.click();
  await save('messages', message.id);
  const storedMessage = await read('messages', message.id);
  expect(storedMessage.configuration.routing.enabled).toBe(false);
  expect(storedMessage.configuration.communication_contract).toEqual(message.configuration.communication_contract);
  expect([storedMessage.cycle_ms, storedMessage.dlc]).toEqual([100, 2]);
  await page.setViewportSize({ width: 1383, height: 1000 });
  await open('signals', signal.id);
  await expect(toggle).toBeChecked();
  await expect(page.getByText('Die übergeordnete Nachricht steht auf Off', { exact: false })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'On · Nachricht Off', exact: true })).toBeVisible();
  await open('messages', message.id);
  await expect(toggle).not.toBeChecked();
  await info.attach('routing-permission-persisted', { body: JSON.stringify({ project, message: storedMessage, signal: await read('signals', signal.id) }), contentType: 'application/json' });
});
