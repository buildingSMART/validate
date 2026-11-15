import { defineConfig, devices } from '@playwright/test';
import { backend, baseURL } from './tests/htmx/urls.js';

export default defineConfig({
  testDir: './tests',
  testMatch: ['htmx/validate.test.js', 'htmx/allowlisting.test.js', 'django_admin.test.js', 'validate_api.test.js'],
  forbidOnly: !!process.env.CI,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  timeout: 60000,
  expect: { timeout: 30000 },
  reporter: [['list'], ['html', { outputFolder: 'playwright-report/htmx', open: 'never' }],
    ['junit', { outputFile: 'test-results/htmx/results.xml' }]],
  outputDir: 'test-results/htmx/artifacts',
  use: { ...devices['Desktop Chrome'], baseURL, trace: 'retain-on-failure',
    screenshot: 'only-on-failure', video: 'retain-on-failure' },
  webServer: {
    cwd: '../backend',
    command: process.env.HTMX_SERVER_COMMAND || 'make start-django',
    env: { FRONTEND_MODE: process.env.FRONTEND_MODE || 'htmx' },
    url: `${backend}/admin/`,
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
