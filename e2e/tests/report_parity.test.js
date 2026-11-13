import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const backend = 'http://localhost:8765';
const frontend = 'http://localhost:3001';
const fixture = () => JSON.parse(readFileSync(new URL('../test-results/report-parity.json', import.meta.url)));

async function expandAll(page, htmx) {
  const report = page.getByTestId('report-content');
  if (htmx) {
    const collapsed = report.locator('details:not([open]) > summary');
    // Use the disclosure control: the heading also contains a copy button.
    while (await collapsed.count()) await collapsed.first().locator('.tree-toggle.when-closed').click();
  } else {
    const collapsed = report.locator('[role="treeitem"][aria-expanded="false"]');
    while (await collapsed.count()) await collapsed.first().locator('.MuiTreeItem-content').first().click();
  }
}

async function reportContent(page) {
  // Use visible DOM text nodes: MUI's invalid <thead><th> structure can make
  // innerText concatenate a heading with the next row. Element boundaries are
  // whitespace, not report content. Outcome row order is deliberately ignored.
  return page.getByTestId('report-content').evaluate((root) => {
    const normalizedBodies = new Map();
    const tables = [];
    for (const table of root.querySelectorAll('table')) {
      const outcomes = [...table.querySelectorAll(':scope > thead th')].some((th) => th.textContent.trim() === 'Severity');
      const rows = [];
      for (const body of table.tBodies) {
        const cells = [...body.rows].map((row) => [...row.cells].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim()));
        if (outcomes) {
          cells.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
          normalizedBodies.set(body, cells.flat().join(' '));
        }
        rows.push(...cells);
      }
      if (rows.length) tables.push(rows);
    }
    const emittedBodies = new Set();
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const parts = [];
    let previousParent = null;
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const parent = node.parentElement;
      if (!parent || parent.closest('script,style,textarea,[hidden]')) continue;
      if (getComputedStyle(parent).visibility === 'hidden') continue;
      const body = parent.closest('tbody');
      if (normalizedBodies.has(body)) {
        if (!emittedBodies.has(body)) parts.push(normalizedBodies.get(body));
        emittedBodies.add(body);
        previousParent = null;
        continue;
      }
      const range = document.createRange();
      range.selectNodeContents(node);
      if (range.getClientRects().length) {
        // React can split one word across adjacent text nodes ("S", "yntax").
        if (parent === previousParent) parts[parts.length - 1] += node.textContent;
        else parts.push(node.textContent);
        previousParent = parent;
      }
    }
    return { text: parts.join(' ').replace(/\s+/g, ' ').trim(), tables };
  });
}

test.beforeEach(async ({ context }) => {
  // Forward the v1 fetches to the real backend; do not mock report payloads or HTML.
  await context.route(`${frontend}/bff/**`, async (route) => {
    const url = route.request().url().replace(frontend, backend);
    const response = await context.request.fetch(url, { headers: route.request().headers() });
    await route.fulfill({ response });
  });
  await context.route('**/*typeform*', (route) => route.abort());
});

async function compareReport(context, page, report) {
  const segment = report.kind === 'normative' ? 'rules' : report.kind;
  const html = await context.newPage();
  await page.goto(`${frontend}/report_${segment}/${report.id}`);
  await expect(page.getByTestId('report-content').locator('h2').first()).toBeVisible();
  await html.goto(`${backend}/v2/report_${segment}/${report.id}`);
  await expect(html.getByTestId('report-content')).toBeVisible();

  for (const includeAll of [false, true]) {
    if (includeAll && ['schema', 'normative', 'industry'].includes(report.kind)) {
      await page.getByTestId('report-content').getByRole('checkbox').check();
      const changed = html.waitForResponse((response) => response.url().includes('include_all=1') && response.request().headers()['hx-request'] === 'true');
      await html.getByRole('checkbox').check();
      await changed;
      await expect(html.getByRole('checkbox')).toBeChecked();
    }
    await expandAll(page, false);
    await expandAll(html, true);
    await expect.poll(async () => reportContent(html)).toEqual(await reportContent(page));
  }
  await html.close();
}

for (const privileged of [false, true]) {
  for (let index = 0; index < 12; index++) {
    test(`case ${index + 1}: v1 and HTMX report content ignoring outcome order (${privileged ? 'source reader' : 'reader'})`, async ({ context, page }) => {
      const data = fixture();
      await context.addCookies([data.cookies[privileged ? 1 : 0]]);
      await compareReport(context, page, data.reports[index]);
    });
  }
}

for (const name of ['allowlisted', 'rich_values']) {
  test(`v1 and HTMX report content ignoring outcome order: ${name}`, async ({ context, page }) => {
    const data = fixture();
    await context.addCookies([data.cookies[0]]);
    await compareReport(context, page, data[name]);
  });
}

test('HTMX pages groups, preserves filtering, and reloads the same report URL', async ({ context, page }) => {
  const data = fixture();
  await context.addCookies([data.cookies[0]]);
  await page.goto(`${backend}/v2/report_rules/${data.pagination}`);
  await expect(page.locator('.pagination')).toContainText('1–10 of 23');
  const next = page.waitForResponse((response) => response.url().includes('page=2') && response.request().headers()['hx-request'] === 'true');
  await page.getByRole('link', { name: 'Go to next page' }).click();
  await next;
  await expect(page.locator('.pagination')).toContainText('11–20 of 23');
  await expect(page.locator('#report-section details')).toHaveCount(10);
  await page.reload();
  await expect(page.getByTestId('report-content')).toBeVisible();
  await expect(page.locator('.pagination')).toContainText('11–20 of 23');
  await page.getByRole('checkbox').check();
  await expect(page.locator('.pagination')).toContainText('1–10 of 23');
});
