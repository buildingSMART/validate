import { defineConfig } from '@playwright/test';

// Run with the project's Python environment active. This suite owns a temporary DB.
export default defineConfig({
  testDir: './tests',
  testMatch: ['report_parity.test.js', 'frontend_v2.test.js'],
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  reporter: [['list']],
  outputDir: 'test-results/report-parity',
  use: { browserName: 'chromium', headless: true, trace: 'retain-on-failure' },
  webServer: [
    {
      cwd: '../backend',
      command: process.env.REPORT_PARITY_SERVER_COMMAND || 'python -m apps.ifc_validation_bff.tests.serve_report_parity',
      url: 'http://localhost:8765/static/report/report.css',
      reuseExistingServer: false,
      timeout: 120000,
    },
    {
      cwd: '../frontend',
      command: 'node node_modules/react-scripts/scripts/start.js',
      env: { PORT: '3001', BROWSER: 'none', REACT_APP_FETCH_PATH: '/bff', PUBLIC_URL: '',
             WDS_SOCKET_PORT: '3001', NODE_ENV: 'development' },
      url: 'http://localhost:3001',
      reuseExistingServer: false,
      timeout: 180000,
    },
  ],
});
