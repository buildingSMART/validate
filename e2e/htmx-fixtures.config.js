import { defineConfig, devices } from '@playwright/test';

const mode = process.env.FRONTEND_MODE || 'htmx';
const origin = 'http://localhost:8765';
const baseURL = process.env.HTMX_BASE_URL || `${origin}${mode === 'react' ? '/v2/' : '/'}`;

export default defineConfig({
  testDir: './tests/htmx',
  testMatch: ['frontend.test.js', 'reports.test.js'],
  forbidOnly: !!process.env.CI,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  timeout: 60000,
  expect: { timeout: 15000 },
  reporter: [['list'], ['junit', { outputFile: 'test-results/htmx-fixtures/results.xml' }]],
  outputDir: 'test-results/htmx-fixtures/artifacts',
  use: { ...devices['Desktop Chrome'], baseURL, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: {
    cwd: '../backend',
    command: process.env.HTMX_FIXTURE_SERVER_COMMAND ||
      'python -m apps.ifc_validation_bff.tests.serve_report_parity',
    env: { FRONTEND_MODE: mode },
    url: `${origin}/static/report/report.css`,
    reuseExistingServer: false,
    timeout: 120000,
  },
});
