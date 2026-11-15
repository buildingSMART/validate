import { test, expect } from '@playwright/test';
import { backend, uiURL } from './urls.js';

test.describe('HTMX Validate WebUI', () => {
  test.beforeEach(async ({ context }) => {
    await context.route('**/*typeform*', (route) => route.abort());
  });

  test('should be able to see the homepage', async ({ page }) => {
    await page.goto(uiURL());
    await expect(page.getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Validation', exact: true })).toBeVisible();
    await expect(page.getByText('Select the IFC file(s) you', { exact: false })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Upload & Validate' })).toBeVisible();
  });

  test('should be able to see the dashboard', async ({ page }) => {
    await page.goto(uiURL());
    await page.getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Validation', exact: true }).click();
    await expect(page).toHaveURL(uiURL('dashboard'));
    await expect(page.getByRole('columnheader', { name: 'File Name', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Upload & Validate' })).toBeVisible();
  });

  test('should set a csrftoken cookie while navigating', async ({ context, page }) => {
    await context.clearCookies();
    await page.goto(uiURL());
    await expect.poll(async () => (await context.cookies(uiURL())).some((cookie) => cookie.name === 'csrftoken')).toBe(true);
  });

  test('should persist self-declaration through the HTMX affiliation endpoint', async ({ context, page }) => {
    await page.goto(uiURL());
    const csrf = (await context.cookies(uiURL())).find((cookie) => cookie.name === 'csrftoken').value;
    const declare = (answer) => page.request.post(uiURL('affiliation'), {
      headers: { 'HX-Request': 'true' },
      form: { is_vendor_self_declared: answer, csrfmiddlewaretoken: csrf },
    });
    try {
      expect((await declare('true')).status()).toBe(200);
      const response = await page.request.get(`${backend}/bff/api/me`);
      expect((await response.json()).user_data.is_vendor_self_declared).toBe(true);
    } finally {
      expect((await declare('false')).status()).toBe(200);
    }
    await page.reload();
    await expect(page.getByRole('dialog')).toHaveCount(0);
  });
});
