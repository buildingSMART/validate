import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';
const BFF_URL = 'http://localhost:8000/bff';

// --- helper to close any blocking MUI dialog/cookie banner/onboarding ---
async function dismissAnyDialog(page) {
  // give the UI a tick to mount any modal
  await page.waitForTimeout(100);

  const dialog = page.getByRole('dialog').first();

  const visible = await dialog.isVisible().catch(() => false);
  if (!visible) return;

  // Try ESC
  await page.keyboard.press('Escape').catch(() => {});

  // Try common buttons
  const btn = dialog.getByRole('button', {
    name: /close|ok|got it|accept|agree|dismiss|continue/i
  });
  if (await btn.isVisible().catch(() => false)) {
    await btn.click().catch(() => {});
  }
}

test.beforeEach(async ({ page }) => {
  // navigate to the Validate Web UI
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
  await dismissAnyDialog(page);
});

test.describe('Validate WebUI Tests', () => {
  test('should be able to see the homepage', async ({ page }) => {
    // click the dashboard link
    await expect(page.getByRole('link', { name: /Validation/i })).toBeVisible();
    await expect(page.getByText(/Select the IFC file\(s\) you/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /Upload & Validate/i })).toBeVisible();
  });

  test('should be able to see the dashboard', async ({ page }) => {
    await page.getByRole('link', { name: /Validation/i }).click();
    // check if certain elements are visible
    // a left-hand side menu, a text element and a column header
    await expect(page.getByRole('link', { name: /Validation/i })).toBeVisible();
    await expect(page.getByText(/Select the IFC file\(s\) you/i)).toBeVisible();
    await expect(page.getByRole('columnheader', { name: /File Name/i })).toBeVisible();
  });

  test('should set a csrftoken cookie while navigating', async ({ page }) => {
    // clear cookies before the test
    await page.context().clearCookies();
    await page.goto(BASE_URL);

    // check for a specific cookie by name; retry with delay if not found

    let csrftoken = '';
    for (let i = 0; i < 5; i++) {
      const cookies = await page.context().cookies();
      csrftoken = cookies.find(c => c.name === 'csrftoken')?.value ?? '';
      if (csrftoken) break;
      await page.waitForTimeout(1000);
    }
    expect(csrftoken).toBeTruthy();
  });

  test('should be able to post back self-declaration', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    // clear cookies before the test
    await page.context().clearCookies();

    // navigate to the Validate Web UI
    await page.goto(BASE_URL);
        
    // wait for a specific cookie by name; retry with delay if not found
    let csrftoken = '';
    for (let i = 0; i < 5; i++) {
      const cookies = await page.context().cookies();
      csrftoken = cookies.find(c => c.name === 'csrftoken')?.value ?? '';
      if (csrftoken) break;
      await page.waitForTimeout(1000);
    }
    expect(csrftoken).toBeTruthy();

    // make request to the BFF API (within browser context, so headers/cookies are sent)
    const response = await page.request.post(`${BFF_URL}/api/me`, {
      data: { is_vendor_self_declared: true },
      headers: { 'X-CSRFToken': csrftoken, 'Content-Type': 'application/json' },
    });

    expect(response.statusText()).toBe('OK');
  });
});
