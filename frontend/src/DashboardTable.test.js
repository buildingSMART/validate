import '@testing-library/jest-dom';
import { render, screen, within } from '@testing-library/react';
import { PageContext } from './Page';
import DashboardTable from './DashboardTable';

const base = (over) => ({
  id: 1, code: 'r000', filename: 'x.ifc', progress: 100, deleted: false,
  date: '2026-08-26T10:00:00Z',
  status_syntax: 'p', status_schema: 'p', status_rules: 'p', status_ind: 'p',
  status_signatures: 'n', status_bsdd: 'p', status_prereq: 'p', status_mvd: 'p',
  ...over,
});

const rows = [
  base({ id: 1, code: 'rMVDONLY', filename: 'mvd_only.ifc',  status_header: 'v', header_validation: { validation_errors: ['description'], mvd: null } }),
  base({ id: 2, code: 'rCLEAN',   filename: 'clean.ifc',     status_header: 'v', header_validation: { validation_errors: [], mvd: 'ReferenceView_V1.2' } }),
  base({ id: 3, code: 'rINVALID', filename: 'invalid.ifc',   status_header: 'i', header_validation: { validation_errors: ['version', 'description'], mvd: null } }),
  base({ id: 4, code: 'rPENDING', filename: 'pending.ifc',   status_header: 'p', header_validation: null, progress: 100 }),
];

beforeEach(() => {
  global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.resolve({ models: rows, count: rows.length }) }));
});

function cellFor(filename) {
  return screen.getByText(filename).closest('td');
}

test('header icon next to filename reflects header policy errors, not only status_header', async () => {
  render(<PageContext.Provider value={{ sandboxId: null }}><DashboardTable /></PageContext.Provider>);
  await screen.findByText('mvd_only.ifc');

  // MVD-only error, status_header still 'v' (scorecard gate) -> warning, linked to file report
  const mvdOnly = cellFor('mvd_only.ifc');
  expect(within(mvdOnly).getAllByTestId('WarningIcon')).toHaveLength(1);
  expect(within(mvdOnly).queryByTestId('InfoIcon')).toBeNull();
  expect(within(mvdOnly).getByRole('link')).toHaveAttribute('href', '/report_file/rMVDONLY');

  // no header errors -> green info icon, no warning
  const clean = cellFor('clean.ifc');
  expect(within(clean).queryByTestId('WarningIcon')).toBeNull();
  expect(within(clean).getAllByTestId('InfoIcon')).toHaveLength(1);

  // marker-field error (status_header 'i') -> warning, unchanged behaviour
  const invalid = cellFor('invalid.ifc');
  expect(within(invalid).getAllByTestId('WarningIcon')).toHaveLength(1);

  // still pending, no header_validation yet -> plain info icon, no crash on null
  const pending = cellFor('pending.ifc');
  expect(within(pending).queryByTestId('WarningIcon')).toBeNull();
  expect(within(pending).getAllByTestId('InfoIcon')).toHaveLength(1);
});

test('sandbox links keep the sandbox prefix', async () => {
  render(<PageContext.Provider value={{ sandboxId: 'sb1' }}><DashboardTable /></PageContext.Provider>);
  await screen.findByText('mvd_only.ifc');
  expect(within(cellFor('mvd_only.ifc')).getByRole('link')).toHaveAttribute('href', '/sandbox/report_file/sb1/rMVDONLY');
});
