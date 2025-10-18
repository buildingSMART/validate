import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:8000/admin';
const TEST_CREDENTIALS = 'root:root';

import { execFileSync } from 'child_process';
import { resolve } from 'path';

async function login(page) {

  // navigate to the Django admin login page
  await page.goto(BASE_URL);
  await page.reload(); // refresh to make sure CSRF token is fresh

  // check if the login form is present
  await expect(page.getByRole('textbox', { name: 'Username:' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Password:' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible();

  // fill in the login form
  const [username, password] = TEST_CREDENTIALS.split(':');
  await page.getByRole('textbox', { name: 'Username:' }).fill(username);
  await page.getByRole('textbox', { name: 'Password:' }).fill(password);

  // submit the form
  await page.getByRole('button', { name: 'Log in' }).click();


  // check if the sidebar is visible - and hide
  if (await page.getByRole('link', { name: 'Hide »' }).isVisible()) {
    await page.getByRole('link', { name: 'Hide »' }).click();
  }
}

async function logout(page) {

  await page.getByRole('button', { name: 'Log out' }).click();
}

test.describe('UI - Django Admin', () => {

  test('should be able to login and logout', async ({ page }) => {

    // login
    await login(page);

    // check if the login was successful
    await expect(page).toHaveURL(`${BASE_URL}/`);
    await expect(page.getByRole('link', { name: 'Django administration' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'IFC VALIDATION' })).toBeVisible();

    // logout
    await logout(page);
  });

  test('navigate to Companies', async ({ page }) => {

    // login
    await login(page);

    // navigate and check elements of the screen
    await page.goto(`${BASE_URL}/ifc_validation_models/company/`);
    await expect(page).toHaveURL(`${BASE_URL}/ifc_validation_models/company/`);
    await expect(page.getByText('Select Company to change')).toBeVisible();
    await expect(page.locator('p.paginator')).toBeVisible();
    await expect(page.locator('p.paginator').getByText(/Compan[ies|y]+/)).toBeVisible();

    // logout
    await logout(page);
  });

  test('navigate to Authoring Tools', async ({ page }) => {

    // login
    await login(page);

    // navigate and check elements of the screen
    await page.goto(`${BASE_URL}/ifc_validation_models/authoringtool/`);
    await expect(page).toHaveURL(`${BASE_URL}/ifc_validation_models/authoringtool/`);
    await expect(page.getByText('Select Authoring Tool to change')).toBeVisible();
    await expect(page.locator('p.paginator')).toBeVisible();
    await expect(page.locator('p.paginator').getByText(/Authoring Tool[s]*/)).toBeVisible();

    // logout
    await logout(page);
  });

  test('navigate to Validation Requests', async ({ page }) => {

    // login
    await login(page);

    // navigate and check elements of the screen
    await page.goto(`${BASE_URL}/ifc_validation_models/validationrequest/`);
    await expect(page).toHaveURL(`${BASE_URL}/ifc_validation_models/validationrequest/`);
    await expect(page.getByText('Select Validation Request to change')).toBeVisible();
    await expect(page.locator('p.paginator')).toBeVisible();
    await expect(page.locator('p.paginator').getByText(/Validation Request[s]*/)).toBeVisible();

    // logout
    await logout(page);
  });

  test('navigate to Models', async ({ page }) => {

    // login
    await login(page);

    // navigate and check elements of the screen
    await page.goto(`${BASE_URL}/ifc_validation_models/model/`);
    await expect(page).toHaveURL(`${BASE_URL}/ifc_validation_models/model/`);
    await expect(page.getByText('Select Model to change')).toBeVisible();
    await expect(page.locator('p.paginator')).toBeVisible();
    await expect(page.locator('p.paginator').getByText(/Model[s]*/)).toBeVisible();

    // logout
    await logout(page);
  });

  test('navigate to Statistics & Charts', async ({ page }) => {

    // login
    await login(page);

    // navigate and check elements of the screen
    await page.goto(`${BASE_URL}/ifc_validation_models/`);
    await expect(page).toHaveURL(`${BASE_URL}/ifc_validation_models/`);
    await expect(page.getByText('Statistics')).toBeVisible();
    await expect(page.getByText('Choose a year')).toBeVisible();

    // check some stats
    await expect(page.getByText('users')).toBeVisible();
    await expect(page.getByText('files processed')).toBeVisible();
    await expect(page.getByText('tools observed')).toBeVisible();

    // check some charts
    await expect(page.locator('#requestsChart')).toBeVisible();
    await expect(page.locator('#processingStatusChart')).toBeVisible();
    await expect(page.locator('#usageByVendorChart')).toBeVisible();
    await expect(page.locator('#topToolsChart')).toBeVisible();
    await expect(page.locator('#queueP95Chart')).toBeVisible();

    // logout
    await logout(page);
  }); 

  test('top bar search for Validation Requests', async ({ page }) => {

    // login
    await login(page);

    // search and check elements
    await page.goto(`${BASE_URL}/ifc_validation_models/validationrequest/?q=test123`);
    await expect(page).not.toHaveURL(`${BASE_URL}/ifc_validation_models/validationrequest/?e=1`); // no error
    await expect(page).toHaveURL(`${BASE_URL}/ifc_validation_models/validationrequest/?q=test123`);
    await expect(page.locator('p.paginator')).toBeVisible();
    await expect(page.locator('p.paginator').getByText(/[0-9]* Validation Request[s]+/)).toBeVisible();

    // logout
    await logout(page);
  });

  test('search Validation Requests by Produced By', async ({ page }) => {

    // login
    await login(page);

    // search and check elements - 0 results
    await page.goto(`${BASE_URL}/ifc_validation_models/validationrequest/?model__produced_by__contains=test123`);
    await expect(page).not.toHaveURL(`${BASE_URL}/ifc_validation_models/validationrequest/?e=1`); // no error
    await expect(page).toHaveURL(`${BASE_URL}/ifc_validation_models/validationrequest/?model__produced_by__contains=test123`);
    await expect(page.locator('p.paginator')).toBeVisible();
    await expect(page.locator('p.paginator').getByText('0 Validation Requests')).toBeVisible();

    // filter pane & heading
    const filterPane = page.getByRole('navigation', { name: 'Filter' });
    await expect(filterPane).toBeVisible();
    await expect(filterPane.getByRole('heading', { name: 'By Produced By' })).toBeVisible();
    
    // input field
    const inputField = await filterPane.locator('input[name="model__produced_by__contains"][type="text"]');
    await expect(inputField).toBeVisible();
    await expect(inputField).toHaveValue('test123');
    await expect(filterPane.getByRole('link', { name: '⨉ Remove' })).toBeVisible();

    // logout
    await logout(page);
  });

  test('search Validation Requests by Created By', async ({ page }) => {

    // login
    await login(page);

    // search and check elements - 0 results
    await page.goto(`${BASE_URL}/ifc_validation_models/validationrequest/?created_by__contains=test123`);
    await expect(page).not.toHaveURL(`${BASE_URL}/ifc_validation_models/validationrequest/?e=1`); // no error
    await expect(page).toHaveURL(`${BASE_URL}/ifc_validation_models/validationrequest/?created_by__contains=test123`);
    await expect(page.locator('p.paginator')).toBeVisible();
    await expect(page.locator('p.paginator').getByText('0 Validation Requests')).toBeVisible();

    // filter pane & heading
    const filterPane = page.getByRole('navigation', { name: 'Filter' });
    await expect(filterPane).toBeVisible();
    await expect(filterPane.getByRole('heading', { name: 'By Created By' })).toBeVisible();
    
    // input field
    const inputField = await filterPane.locator('input[name="created_by__contains"][type="text"]');
    await expect(inputField).toBeVisible();
    await expect(inputField).toHaveValue('test123');
    await expect(filterPane.getByRole('link', { name: '⨉ Remove' })).toBeVisible();

    // logout
    await logout(page);
  });

  test('search Models by Produced By', async ({ page }) => {

    // login
    await login(page);

    // search and check elements - 0 results
    await page.goto(`${BASE_URL}/ifc_validation_models/model/?produced_by__contains=test123`);
    await expect(page).not.toHaveURL(`${BASE_URL}/ifc_validation_models/model/?e=1`); // no error
    await expect(page).toHaveURL(`${BASE_URL}/ifc_validation_models/model/?produced_by__contains=test123`);
    await expect(page.locator('p.paginator')).toBeVisible();
    await expect(page.locator('p.paginator').getByText('0 Models')).toBeVisible();

    // filter pane & heading
    const filterPane = page.getByRole('navigation', { name: 'Filter' });
    await expect(filterPane).toBeVisible();
    await expect(filterPane.getByRole('heading', { name: 'By Produced By' })).toBeVisible();
    
    // input field
    const inputField = await filterPane.locator('input[name="produced_by__contains"][type="text"]');
    await expect(inputField).toBeVisible();
    await expect(inputField).toHaveValue('test123');
    await expect(filterPane.getByRole('link', { name: '⨉ Remove' })).toBeVisible();

    // logout
    await logout(page);
  });

  test('search Models by Digital Signatures', async ({ page }) => {

    // login
    await login(page);

    // search and check elements - 0 results
    await page.goto(`${BASE_URL}/ifc_validation_models/model/?status_signatures__exact=v`);
    await expect(page).not.toHaveURL(`${BASE_URL}/ifc_validation_models/model/?e=1`); // no error
    await expect(page).toHaveURL(`${BASE_URL}/ifc_validation_models/model/?status_signatures__exact=v`);
    await expect(page.locator('p.paginator')).toBeVisible();
    await expect(page.locator('p.paginator').getByText(/Model[s]*/)).toBeVisible();

    // filter pane & heading
    const filterPane = page.getByRole('navigation', { name: 'Filter' });
    await expect(filterPane).toBeVisible();
    await expect(filterPane.getByText('By status signatures')).toBeVisible();

    // logout
    await logout(page);
  });

  test('Queue (sec) is derived from created/started (exact value)', async ({ page }) => {
    const ROOT = resolve(process.cwd(), '..');
    const PYTHON_BIN = resolve(ROOT, 'backend/.dev/venv/bin/python');
    const FILE = `queue-e2e-${Date.now()}.ifc`;
  
    execFileSync(
      PYTHON_BIN,
      [
        'backend/manage.py', 'seed_vr',
        '--file', FILE,
        '--created', '2025-01-01T00:00:00Z',
        '--started', '2025-01-01T00:01:15Z',
      ],
      { cwd: ROOT, stdio: 'inherit' }
    );
  
    await login(page);
  
    await page.goto(`${BASE_URL}/ifc_validation_models/validationrequest/?q=${FILE}`);
  
    const row = page.locator('#result_list tbody tr', { hasText: FILE });
    const cell = row.locator('td.field-queue_time_text b');
  
    await expect(row).toBeVisible();
    await expect(cell).toHaveText(/^75(\.0)?$/);
  
    await logout(page);
  });

});