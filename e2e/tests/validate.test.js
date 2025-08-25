import { test, expect, request } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';
const BFF_URL = 'http://localhost:8000/bff';

test.describe('Validate WebUI Tests', () => {

  test('should be able to see the homepage', async ({ page }) => {

    // navigate to the Validate Web UI
    await page.goto(BASE_URL);
    
    // check if certain elements are visible
    // a left-hand side menu, a text element and an upload button
    await expect(page.getByRole('link', { name: 'Validation' })).toBeVisible();
    await expect(page.getByText('Select the IFC file(s) you')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Upload & Validate' })).toBeVisible();    
  });

  test('should be able to see the dashboard', async ({ page }) => {

    // navigate to the Validate Web UI
    await page.goto(BASE_URL);

    // click the dashboard link
    await page.getByRole('link', { name: 'Validation' }).click();
    
    // check if certain elements are visible
    // a left-hand side menu, a text element and a column header
    await expect(page.getByRole('link', { name: 'Validation' })).toBeVisible();
    await expect(page.getByText('Select the IFC file(s) you')).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'File Name' })).toBeVisible();    
  });

  test('should set a crsftoken cookie while navigating', async ({ page }) => {

    // clear cookies before the test
    await page.context().clearCookies();

    // navigate to the Validate Web UI
    await page.goto(BASE_URL);
    
    // check for a specific cookie by name; retry with delay if not found
    let retries = 5;
    let cookies = [];
    const cookieName = 'csrftoken';
    for (let i = 0; i < retries; i++) {
      cookies = await page.context().cookies();
      if (cookies.some(cookie => cookie.name === cookieName)) break;
      await page.waitForTimeout(1000);
    };
    expect(cookies.some(cookie => cookie.name === cookieName)).toBeTruthy();
  });

  test('should be able to post back self-declaration', async ({ browser }) => {
    
    const context = await browser.newContext();
    const page = await context.newPage();

    // clear cookies before the test
    await page.context().clearCookies();
    
    // navigate to the Validate Web UI
    await page.goto(BASE_URL);
        
    // wait for a specific cookie by name; retry with delay if not found
    let retries = 5;
    let cookies = [];
    const cookieName = 'csrftoken';
    for (let i = 0; i < retries; i++) {
      cookies = await page.context().cookies();
      if (cookies.some(cookie => cookie.name === cookieName)) break;
      await page.waitForTimeout(1000);
    };
    let csrftoken = cookies.find(cookie => cookie.name === cookieName)?.value;   

    // make request to the BFF API (within browser context, so headers/cookies are sent)
    const response = await page.request.post(BFF_URL + '/api/me', {
      method: 'POST',
        data: JSON.stringify({ is_vendor_self_declared: 'True' }),
        headers: { 
            'x-csrf-token': csrftoken,
            'Content-Type': 'application/json',
        },
        credentials: 'include'
    });

    expect(response.statusText()).toBe('OK');
  });
  
});