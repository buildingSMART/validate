import { test, expect } from '@playwright/test';
import { fixture, uiURL } from './fixtures.js';

async function expandAll(page) {
  const collapsed = page.getByTestId('report-content').locator('details:not([open]) > summary');
  while (await collapsed.count()) await collapsed.first().locator('.tree-toggle.when-closed').click();
}

test.beforeEach(async ({ context }) => {
  await context.route('**/*typeform*', (route) => route.abort());
});

for (const privileged of [false, true]) {
  for (let index = 0; index < 12; index++) {
    test(`report case ${index + 1} renders, filters and reloads (${privileged ? 'source reader' : 'reader'})`, async ({ context, page }) => {
      const data = fixture();
      const report = data.reports[index];
      await context.addCookies([data.cookies[privileged ? 1 : 0]]);
      const segment = report.kind === 'normative' ? 'rules' : report.kind;
      const response = await page.goto(uiURL(`report_${segment}/${report.id}`));
      expect(response.status()).toBe(200);
      const content = page.getByTestId('report-content');
      await expect(content).toBeVisible();
      await expect(content).toContainText(report.file_name);
      await expandAll(page);
      if (['schema', 'normative', 'industry'].includes(report.kind)) {
        const filter = page.getByRole('checkbox', { name: /include Passed/ });
        const swapped = page.waitForResponse((response) => response.url().includes('include_all=1') &&
          response.request().headers()['hx-request'] === 'true');
        await filter.check();
        expect((await swapped).status()).toBe(200);
        await expect(filter).toBeChecked();
        await expandAll(page);
        await page.reload();
        await expect(filter).toBeChecked();
      }
      if (index === 5) {
        await expandAll(page);
        await expect(content).toContainText('SLIDING_TO_RIGHT');
        if (privileged) await expect(content).toContainText('#22=IFCDOOR($);');
        else await expect(content).not.toContainText('#22=IFCDOOR($);');
      }
      if (index === 11) await expect(content).toContainText('Only the first 10 occurrences');
      await expect(content).toContainText(report.file_name);
    });
  }
}

test('allowlisted findings retain their original and effective severity', async ({ context, page }) => {
  const data = fixture();
  await context.addCookies([data.cookies[0]]);
  await page.goto(uiURL(`report_rules/${data.allowlisted.id}`));
  await expect(page.locator('#report-section')).not.toContainText('ALW001');
  await page.getByRole('checkbox', { name: /include Passed/ }).check();
  await expect(page.locator('#report-section')).toContainText('ALW001');
  await expandAll(page);
  await expect(page.locator('[data-severity-in-db="4"][data-severity-after-whitelisting="2"]').first()).toBeVisible();
  await expect(page.locator('#report-section')).toContainText('Allowlisted');
});

test('rule findings render entity, GUID, measurement and fallback values', async ({ context, page }) => {
  const data = fixture();
  await context.addCookies([data.cookies[0]]);
  await page.goto(uiURL(`report_rules/${data.rich_values.id}`));
  await expandAll(page);
  for (const text of ['VAL001', 'VAL002', 'VAL003', 'VAL004', 'VAL005', 'IfcBeam', 'bad!?', 'unknown', 'shape']) {
    await expect(page.getByTestId('report-content')).toContainText(text);
  }
});

test('report pagination preserves filtering and the URL through HTMX swaps and reloads', async ({ context, page }) => {
  const data = fixture();
  await context.addCookies([data.cookies[0]]);
  await page.goto(uiURL(`report_rules/${data.pagination}`));
  await expect(page.locator('.pagination')).toContainText('1–10 of 23');
  const swapped = page.waitForResponse((response) => response.url().includes('page=2') &&
    response.request().headers()['hx-request'] === 'true');
  await page.getByRole('link', { name: 'Go to next page' }).click();
  expect((await swapped).status()).toBe(200);
  await expect(page.locator('.pagination')).toContainText('11–20 of 23');
  await expect(page.locator('#report-section details')).toHaveCount(10);
  await page.reload();
  await expect(page.locator('.pagination')).toContainText('11–20 of 23');
  await page.getByRole('checkbox', { name: /include Passed/ }).check();
  await expect(page.locator('.pagination')).toContainText('1–10 of 23');
});
