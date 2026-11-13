import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import HeaderResult, { headerFindings } from './HeaderResult';

const details = [
  { field: 'originating_system', expected: 'Software Company Name - Application Name - Application Version', observed: 'synthetic test file for allowlist' },
  { field: 'company_name', expected: 'Software Company Name from Originating System: not empty, no dashes, no leading or trailing whitespace', observed: null },
  { field: 'description', expected: 'One of the MVDs valid for IFC4X3_ADD2: ReferenceView, Alignment-basedView', observed: 'CoordinationView' },
  { field: 'description', expected: 'Exactly one base MVD (add-on views excluded)', observed: 'CoordinationView, ReferenceView' },
  { field: 'application_name', expected: 'Application Name from Originating System: not empty, no dashes, no leading or trailing whitespace', observed: '  Revit' },
];

test('shows expected vs observed per header field', () => {
  render(<HeaderResult summary="Header Policy" status="v"
    headerValidation={{ validation_errors: details.map(d => d.field), validation_details: details }} />);

  expect(screen.getByText('Header Policy')).toBeInTheDocument();
  expect(screen.getByText('Originating System')).toBeInTheDocument();
  expect(screen.getByText('Software Company Name - Application Name - Application Version')).toBeInTheDocument();
  expect(screen.getByText('synthetic test file for allowlist')).toBeInTheDocument();
  // a value the policy could not derive
  expect(screen.getByText('missing')).toBeInTheDocument();
  // two findings on the same field are grouped
  expect(screen.getByText(/occurred 2 times/)).toBeInTheDocument();
  expect(screen.getByText('CoordinationView, ReferenceView')).toBeInTheDocument();
  // leading whitespace made visible
  expect(screen.getByText('□□Revit')).toBeInTheDocument();
  // all header findings are warnings
  expect(screen.getAllByText('Warning')).toHaveLength(details.length);
  expect(screen.queryByText('Valid')).toBeNull();
});

test('falls back to field names for reports validated without details', () => {
  render(<HeaderResult summary="Header Policy" status="v"
    headerValidation={{ validation_errors: ['description'], mvd: 'CoordinationView' }} />);

  expect(screen.getByText('MVD(s)')).toBeInTheDocument();
  expect(screen.getByText('See header policy')).toHaveAttribute('href', expect.stringContaining('#description'));
  expect(screen.getByText('CoordinationView')).toBeInTheDocument();
});

test('shows the header status when there are no findings', () => {
  render(<HeaderResult summary="Header Policy" status="v" headerValidation={{ validation_errors: [], validation_details: [] }} />);
  expect(screen.getByText('Valid')).toBeInTheDocument();

  render(<HeaderResult summary="Header Policy" status="p" headerValidation={null} />);
  expect(screen.getByText('Pending...')).toBeInTheDocument();
});

test('headerFindings prefers details and falls back to stored field values', () => {
  expect(headerFindings(null)).toEqual([]);
  expect(headerFindings({ validation_errors: ['version'], version: '1.0 ' })).toEqual([{ field: 'version', expected: null, observed: '1.0 ' }]);
  expect(headerFindings({ validation_errors: ['version'], validation_details: details })).toBe(details);
});
