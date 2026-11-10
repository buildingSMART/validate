import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const backend = 'http://localhost:8765';
const frontend = 'http://localhost:3001';
const fixture = () => JSON.parse(readFileSync(new URL('../test-results/report-parity.json', import.meta.url)));

test.beforeEach(async ({ context }) => {
  await context.route(`${frontend}/bff/**`, async (route) => {
    const response = await context.request.fetch(route.request().url().replace(frontend, backend), { headers: route.request().headers() });
    await route.fulfill({ response });
  });
  await context.route('**/*typeform*', (route) => route.abort());
});

test('anonymous landing page retains the current content and offers sign-in', async ({ context, page }) => {
  const legacy = await context.newPage();
  await legacy.goto(frontend);
  await page.goto(`${backend}/v2/`);
  const phrases = ['IFC Validation Service', 'Four layers of validation', 'Three simple steps', 'Common questions', 'Go deeper',
    'STEP Syntax', 'IFC Schema', 'Normative Rules', 'Industry Practices', 'Is the Validation Service free?', 'What IFC schema versions are supported?'];
  for (const phrase of phrases) {
    await expect(legacy.getByText(phrase, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(phrase, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByRole('link', { name: 'Sign in to start validating →' })).toHaveAttribute('href', '/v2/login');
  await expect(page.getByLabel('Select IFC files')).toHaveCount(0);
  await page.locator('.faq').first().locator('summary').click();
  await expect(page.getByText('Yes. The service is free and provided by buildingSMART international to improve interoperability of IFC.')).toBeVisible();
  await legacy.close();
});

test('authenticated landing page and navigation stay within v2', async ({ context, page }) => {
  await context.addCookies([fixture().cookies[0]]);
  await page.goto(`${backend}/v2/`);
  await expect(page.locator('#ifc_dropzone .dz-message')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Upload & Validate' })).toBeVisible();
  const links = await page.locator('a[href^="/"]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('href')));
  expect(links.every((href) => href.startsWith('/v2/'))).toBeTruthy();
  await page.getByRole('link', { name: 'Go to dashboard →' }).click();
  await expect(page).toHaveURL(`${backend}/v2/dashboard`);
  await expect(page.getByTestId('dashboard-content')).toBeVisible();
});

test('dashboard filenames and validation status icons agree with v1', async ({ context, page }) => {
  await context.addCookies([fixture().cookies[0]]);
  const legacy = await context.newPage();
  await legacy.goto(`${frontend}/dashboard`);
  await expect(legacy.locator('tbody tr')).toHaveCount(5);
  await page.goto(`${backend}/v2/dashboard`);
  await expect(page.locator('.dashboard-table tbody tr')).toHaveCount(5);
  await page.screenshot({ path: test.info().outputPath('dashboard-v2.png'), fullPage: true });
  const statuses = async (locator, attribute) => locator.evaluateAll((rows, attribute) => rows.map((row) =>
    [...row.querySelectorAll('td')].slice(2, 6).map((cell) => cell.querySelector(`[${attribute}]`)?.getAttribute(attribute))), attribute);
  expect(await statuses(page.locator('.dashboard-table tbody tr'), 'data-status-icon')).toEqual(
    await statuses(legacy.locator('tbody tr'), 'data-testid'));
  // Compare the actual Material SVG geometry, including pending/not-validated states.
  const legacyPaths = await legacy.locator('tbody tr').evaluateAll((rows) => rows.map((row) =>
    [...row.querySelectorAll('td')].slice(2, 6).map((cell) =>
      [...cell.querySelectorAll('svg path')].map((path) => path.getAttribute('d')))));
  const htmlPaths = await page.locator('.dashboard-table tbody tr').evaluateAll(async (rows) => {
    const use = rows[0].querySelector('use');
    const sprite = new DOMParser().parseFromString(await (await fetch(use.getAttribute('href').split('#')[0])).text(), 'image/svg+xml');
    return rows.map((row) => [...row.querySelectorAll('td')].slice(2, 6).map((cell) => {
      const id = cell.querySelector('use').getAttribute('href').split('#')[1];
      return [...sprite.getElementById(id).querySelectorAll('path')].map((path) => path.getAttribute('d'));
    }));
  });
  expect(htmlPaths).toEqual(legacyPaths);
  const htmlLink = page.locator('.header-status').first();
  const legacyLink = legacy.locator('tbody tr').first().locator('a.MuiIconButton-root').first();
  const appearance = (link) => link.evaluate((node) => {
    const css = getComputedStyle(node);
    return { radius: css.borderRadius, shadow: css.boxShadow };
  });
  expect(await appearance(htmlLink)).toEqual(await appearance(legacyLink));
  await legacyLink.hover();
  await expect.poll(async () => (await appearance(legacyLink)).shadow).toContain('0.3');
  await htmlLink.hover();
  await expect.poll(() => appearance(htmlLink)).toEqual(await appearance(legacyLink));
  await htmlLink.focus();
  await expect(htmlLink).toBeFocused();
  expect(await htmlLink.evaluate((node) => getComputedStyle(node).outlineStyle)).toBe('solid');
  const models = await (await context.request.get(`${backend}/bff/api/models_paginated/0/5`)).json();
  for (const model of models.models) await expect(page.getByText(model.filename, { exact: false }).first()).toBeVisible();
  const popupEvent = page.waitForEvent('popup');
  await page.getByRole('link', { name: /^File information for/ }).first().click();
  const report = await popupEvent;
  await expect(report).toHaveURL(/\/v2\/report_file\//);
  await expect(report.getByTestId('report-content')).toBeVisible();
  await report.close();
  await legacy.close();
});

test('dashboard pages and polling preserve the selection and disable running files', async ({ context, page }) => {
  await context.addCookies([fixture().cookies[0]]);
  await page.goto(`${backend}/v2/dashboard`);
  const running = page.locator('tr').filter({ hasText: 'dashboard-running.ifc' });
  await expect(running.getByRole('checkbox')).toBeDisabled();
  const pending = page.getByRole('checkbox', { name: 'Select dashboard-pending.ifc', exact: true });
  await pending.check();
  await expect(page.locator('[data-selection-count]')).toHaveText('1 selected');
  const oldPanel = await page.locator('#dashboard-panel').elementHandle();
  await page.waitForResponse((response) => response.request().method() === 'GET' && response.url().includes('/v2/dashboard') && response.request().headers()['hx-request'] === 'true');
  await page.waitForFunction((panel) => !panel.isConnected, oldPanel);
  await expect(pending).toBeChecked();
  await page.getByRole('combobox', { name: 'Rows per page' }).selectOption('10');
  await expect(page.locator('.dashboard-table tbody tr')).toHaveCount(10);
  await page.getByRole('link', { name: 'Go to next page' }).click();
  await expect(page).toHaveURL(/page=2/);
  await page.reload();
  await expect(page.getByTestId('dashboard-content')).toBeVisible();
});

test('Dropzone matches v1 options and supports drag/drop, removal and file limits', async ({ context, page }) => {
  await context.addCookies([fixture().cookies[0]]);
  const legacy = await context.newPage();
  await legacy.goto(`${frontend}/dashboard`);
  await page.goto(`${backend}/v2/`);
  const options = async (target) => {
    await target.waitForFunction(() => document.getElementById('ifc_dropzone')?.dropzone);
    return target.evaluate(() => {
      const { options } = document.getElementById('ifc_dropzone').dropzone;
      return Object.fromEntries(['uploadMultiple', 'acceptedFiles', 'parallelUploads', 'maxFiles',
        'maxFilesize', 'autoProcessQueue', 'addRemoveLinks', 'withCredentials'].map((key) => [key, options[key]]));
    });
  };
  expect(await options(page)).toEqual(await options(legacy));
  await page.evaluate(() => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(['IFC'], 'dropped.ifc'));
    document.getElementById('ifc_dropzone').dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: transfer }));
  });
  await expect(page.locator('.dz-filename')).toHaveText('dropped.ifc');
  await page.getByRole('link', { name: 'Remove file' }).click();
  await expect(page.locator('.dz-preview')).toHaveCount(0);
  await page.evaluate(() => {
    const file = new File(['IFC'], 'oversized.ifc');
    Object.defineProperty(file, 'size', { value: 257 * 1024 * 1024 });
    document.getElementById('ifc_dropzone').dropzone.addFile(file);
  });
  await expect(page.getByRole('alert')).toContainText('larger than 256 MB');
  await expect(page.locator('.dz-preview')).toHaveCount(0);
  await page.evaluate(() => {
    const dz = document.getElementById('ifc_dropzone').dropzone;
    for (let i = 0; i < 101; i++) dz.addFile(new File(['IFC'], `limit-${i}.ifc`));
  });
  await expect(page.getByRole('alert')).toContainText('can not upload any more files');
  expect(await page.evaluate(() => document.getElementById('ifc_dropzone').dropzone.getAcceptedFiles().length)).toBe(100);
  await page.getByRole('link', { name: 'Remove file' }).evaluateAll((links) => links.forEach((link) => link.click()));
  await expect(page.locator('.dz-preview')).toHaveCount(0);
});

test('Dropzone displays server batch validation errors without navigating away', async ({ context, page }) => {
  await context.addCookies([fixture().cookies[0]]);
  await page.goto(`${backend}/v2/dashboard`);
  // Bypass browser acceptance to exercise the real server boundary.
  await page.evaluate(() => { document.getElementById('ifc_dropzone').dropzone.options.acceptedFiles = null; });
  await page.locator('input.dz-hidden-input').setInputFiles([
    { name: 'rejected-batch.ifc', mimeType: 'application/octet-stream', buffer: Buffer.from('IFC') },
    { name: 'rejected-batch.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('bad') },
  ]);
  const response = page.waitForResponse((response) => response.url().endsWith('/v2/upload'));
  await page.getByRole('button', { name: 'Upload & Validate' }).click();
  expect((await response).status()).toBe(422);
  await expect(page.getByRole('alert')).toContainText('only .ifc files');
  await expect(page.locator('.dz-preview.dz-error')).toHaveCount(2);
  await expect(page.getByRole('button', { name: 'Upload & Validate' })).toBeEnabled();
  await page.reload();
  await expect(page.locator('.dashboard-table')).not.toContainText('rejected-batch.ifc');
});

test('upload rejects invalid files and accepts a batch; individual and bulk deletion work', async ({ context, page }) => {
  await context.addCookies([fixture().cookies[0]]);
  await page.goto(`${backend}/v2/dashboard`);
  await page.locator('input.dz-hidden-input').setInputFiles({ name: 'rejected.txt', mimeType: 'text/plain', buffer: Buffer.from('bad') });
  await expect(page.getByRole('alert').filter({ hasText: "can't upload files of this type" })).toBeVisible();
  // The error tooltip overlaps the link on hover; keyboard activation still removes the file.
  await page.getByRole('link', { name: 'Remove file' }).focus();
  await page.keyboard.press('Enter');
  await page.locator('input.dz-hidden-input').setInputFiles([
    { name: 'browser-first.ifc', mimeType: 'application/octet-stream', buffer: Buffer.from('ISO-10303-21;') },
    { name: 'browser-second.ifc', mimeType: 'application/octet-stream', buffer: Buffer.from('ISO-10303-21;') },
  ]);
  await expect(page.locator('.dz-preview')).toHaveCount(2);
  await expect(page.locator('.dashboard-table')).not.toContainText('browser-first.ifc');
  await page.getByRole('button', { name: 'Upload & Validate' }).click();
  await expect(page).toHaveURL(`${backend}/v2/dashboard`);
  const first = page.locator('.dashboard-table tr').filter({ hasText: 'browser-first.ifc' });
  const second = page.locator('.dashboard-table tr').filter({ hasText: 'browser-second.ifc' });
  await expect(first).toBeVisible();
  await expect(second).toBeVisible();
  await expect(first).toContainText('in queue');
  await second.getByRole('checkbox').check();
  page.once('dialog', (dialog) => dialog.accept());
  await first.getByRole('button', { name: 'Delete browser-first.ifc', exact: true }).click();
  await expect(first).toHaveCount(0);
  await expect(second).toBeVisible();
  await second.getByRole('checkbox').check();
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: 'Delete selected', exact: true }).click();
  await expect(second).toHaveCount(0);
});

test('affiliation declaration persists, then logout returns to the anonymous v2 page', async ({ context, page }) => {
  await context.addCookies([fixture().accounts.declaration]);
  await page.goto(`${backend}/v2/dashboard`);
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await dialog.getByRole('radio', { name: 'I am a regular user, and NOT affiliated with any software company implementing IFC' }).check();
  await dialog.getByRole('button', { name: 'Continue' }).click();
  await expect(dialog).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.locator('.account-menu > summary').click();
  await page.getByRole('button', { name: 'Logout', exact: true }).click();
  await expect(page).toHaveURL(`${backend}/v2/`);
  await expect(page.getByRole('link', { name: 'Sign In', exact: true })).toBeVisible();
});

test('allowlist, scorecards, waiting zone and legacy redirects are available', async ({ context, page }) => {
  await context.addCookies([fixture().cookies[0]]);
  await page.goto(`${backend}/v2/allowlist`);
  await expect(page.getByRole('heading', { name: 'Allowlist', exact: true })).toBeVisible();
  await expect(page.getByText('Browser parity known exception')).toBeVisible();
  await page.goto(`${backend}/v2/scorecards`);
  await expect(page.getByRole('heading', { name: 'Scorecards Service', exact: true })).toBeVisible();
  await expect(page.getByAltText('Screenshot of the buildingSMART Scorecards Service')).toBeVisible();
  await page.goto(`${backend}/v2/waiting_zone`);
  await expect(page.getByRole('heading', { name: 'Awaiting User Activation' })).toBeVisible();
  const report = fixture().reports[0];
  await page.goto(`${backend}/bff/report/${report.id}?type=syntax`);
  await expect(page).toHaveURL(`${backend}/v2/report_syntax/${report.id}`);
});

test('dashboard downloads the stored full PDF report', async ({ context, page }) => {
  await context.addCookies([fixture().cookies[0]]);
  await page.goto(`${backend}/v2/dashboard?per_page=25`);
  const row = page.locator(`[data-request-id="${fixture().rich_values.id}"]`);
  const downloadEvent = page.waitForEvent('download');
  await row.getByRole('link', { name: /^Download full PDF report for/ }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toMatch(/-validation-report\.pdf$/);
  expect(readFileSync(await download.path()).subarray(0, 5).toString()).toBe('%PDF-');
});

test('inactive account is directed to the v2 waiting zone', async ({ context, page }) => {
  await context.addCookies([fixture().accounts.inactive]);
  await page.goto(`${backend}/v2/dashboard`);
  await expect(page).toHaveURL(`${backend}/v2/waiting_zone`);
  await expect(page.getByRole('heading', { name: 'Awaiting User Activation' })).toBeVisible();
});
