import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

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
  
});