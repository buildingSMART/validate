import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:8000/admin';

test.describe('Django Admin Tests', () => {

  test('should be able to login and logout', async ({ page }) => {

    // navigate to the Django admin login page
    await page.goto(BASE_URL);

    // check if the login form is present
    await expect(page.getByRole('textbox', { name: 'Username:' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Password:' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible();

    // fill in the login form
    await page.getByRole('textbox', { name: 'Username:' }).fill('root');
    await page.getByRole('textbox', { name: 'Password:' }).fill('root');

    // submit the form
    await page.getByRole('button', { name: 'Log in' }).click();

    // check if the login was successful
    await expect(page).toHaveURL(`${BASE_URL}/`);
    await expect(page.getByRole('link', { name: 'Django administration' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'IFC VALIDATION' })).toBeVisible();

    // check if the sidebar is visible
    if (await page.getByRole('link', { name: 'Hide »' }).isVisible()) {
      await page.getByRole('link', { name: 'Hide »' }).click();
    }

    // logout
    await page.getByRole('button', { name: 'Log out' }).click();
  });
  
});