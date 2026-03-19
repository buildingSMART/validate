import { test, expect } from '@playwright/test';
import { readFileSync } from 'fs';
import { basename, extname, resolve } from 'path';

const BASE_URL = 'http://localhost:3000';
const BFF_URL = 'http://localhost:8000/bff';

const STATUS_COLUMNS = {
  schema: 3,
  rules: 4,
};

const STATUS_ICONS = {
  v: 'CheckCircleIcon',
  i: 'ErrorIcon',
};

const ALLOWLISTING_CASES = [
  {
    fixturePath: 'fixtures/allowlisting/allowlisted_proxyqto.ifc',
    expectedSchema: 'v',
    expectedRules: 'v',
  },
  {
    fixturePath: 'fixtures/allowlisting/allowlisted_storeyqto.ifc',
    expectedSchema: 'v',
    expectedRules: 'v',
  },
  {
    fixturePath: 'fixtures/allowlisting/not_allowlisted_storeyqto.ifc',
    expectedSchema: 'v',
    expectedRules: 'i',
  },
  {
    fixturePath: 'fixtures/allowlisting/allowlisted_transformertype.ifc',
    expectedSchema: 'v',
    expectedRules: 'v',
  },
  {
    fixturePath: 'fixtures/allowlisting/not_allowlisted_transformertype.ifc',
    expectedSchema: 'i',
    expectedRules: 'v',
  },
];

let createdModelIds = [];

function createUploadPayload(fixturePath) {
  const absolutePath = resolve(process.cwd(), fixturePath);
  const originalName = basename(fixturePath);
  const extension = extname(originalName);
  const stem = originalName.slice(0, -extension.length);
  const uniqueSuffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  return {
    buffer: readFileSync(absolutePath),
    uploadName: `${stem}-${uniqueSuffix}${extension}`,
  };
}

async function gotoDashboard(page) {
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'networkidle' });
  await expect(page.getByRole('columnheader', { name: 'File Name' })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole('button', { name: 'Upload & Validate' })).toBeVisible();
  await expect(page.locator('input[type="file"]').first()).toBeAttached();
}

async function uploadFixture(page, fixturePath) {
  const { buffer, uploadName } = createUploadPayload(fixturePath);

  await gotoDashboard(page);
  await page.locator('input[type="file"]').first().setInputFiles({
    name: uploadName,
    mimeType: 'application/octet-stream',
    buffer,
  });
  await page.getByRole('button', { name: 'Upload & Validate' }).click();

  const row = page.locator('tbody tr').filter({ hasText: uploadName }).first();
  await expect(row).toBeVisible({ timeout: 60_000 });

  return uploadName;
}

async function getModelByFilename(page, fileName) {
  const response = await page.request.get(`${BFF_URL}/api/models_paginated/0/25`);
  expect(response.ok()).toBeTruthy();

  const data = await response.json();
  return data.models.find((model) => model.filename === fileName) ?? null;
}

async function waitForCompletedModel(page, fileName) {
  let latestModel = null;

  await expect
    .poll(
      async () => {
        latestModel = await getModelByFilename(page, fileName);
        return latestModel?.progress ?? 'missing';
      },
      {
        timeout: 180_000,
        intervals: [1_000, 2_000, 5_000],
      }
    )
    .toBe(100);

  return latestModel;
}

async function expectStatusIcon(row, columnKey, status) {
  const iconTestId = STATUS_ICONS[status];
  const cell = row.locator('td').nth(STATUS_COLUMNS[columnKey]);

  await expect(cell.locator(`[data-testid="${iconTestId}"]`)).toBeVisible();
}

async function deleteCreatedModels(page) {
  if (createdModelIds.length === 0) {
    return;
  }

  const cookies = await page.context().cookies();
  const csrfToken = cookies.find((cookie) => cookie.name === 'csrftoken')?.value;

  if (!csrfToken) {
    createdModelIds = [];
    return;
  }

  const response = await page.request.delete(`${BFF_URL}/api/delete/${createdModelIds.join(',')}`, {
    headers: {
      'x-csrf-token': csrfToken,
    },
  });

  expect(response.ok()).toBeTruthy();
  createdModelIds = [];
}

test.describe('UI - Allowlisting dashboard statuses', () => {
  test.describe.configure({ mode: 'serial' });

  test.afterEach(async ({ page }) => {
    await deleteCreatedModels(page);
  });

  for (const allowlistingCase of ALLOWLISTING_CASES) {
    test(`shows the expected schema and rules status for ${basename(allowlistingCase.fixturePath)}`, async ({ page }) => {
      test.slow();

      const uploadedFileName = await uploadFixture(page, allowlistingCase.fixturePath);
      const model = await waitForCompletedModel(page, uploadedFileName);

      expect(model).not.toBeNull();
      createdModelIds.push(model.id);

      expect(model.status_schema).toBe(allowlistingCase.expectedSchema);
      expect(model.status_rules).toBe(allowlistingCase.expectedRules);

      await gotoDashboard(page);

      const row = page.locator('tbody tr').filter({ hasText: uploadedFileName }).first();
      await expect(row).toBeVisible();
      await expectStatusIcon(row, 'schema', allowlistingCase.expectedSchema);
      await expectStatusIcon(row, 'rules', allowlistingCase.expectedRules);
    });
  }
});
