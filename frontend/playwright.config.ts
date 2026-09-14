import { defineConfig } from 'playwright/test';

const baseURL = process.env.NIS_E2E_URL;
if (!baseURL || process.env.NIS_E2E_ISOLATED !== '1') {
  throw new Error('Use scripts/run-release-gate.py: E2E requires a disposable stack.');
}
const endpoint = new URL(baseURL);
if (!['127.0.0.1', 'localhost'].includes(endpoint.hostname) || ['13500', '15050', ''].includes(endpoint.port)) {
  throw new Error('E2E refuses the product address or an unverified remote endpoint.');
}

export default defineConfig({
  testDir: './e2e',
  timeout: 20 * 60_000,
  expect: { timeout: 30_000 },
  workers: 1,
  fullyParallel: false,
  retries: 0,
  forbidOnly: true,
  outputDir: process.env.NIS_E2E_OUTPUT || './test-results',
  reporter: [['list'], ['json', { outputFile: process.env.NIS_E2E_REPORT || './test-results/report.json' }]],
  use: {
    baseURL,
    ...(process.env.NIS_E2E_BROWSER_CHANNEL ? { channel: process.env.NIS_E2E_BROWSER_CHANNEL } : {}),
    viewport: { width: 1383, height: 1000 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 30_000,
  },
});
