import * as React from 'react';
import { TreeView, TreeItem } from '@mui/x-tree-view';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import { statusToColor, statusToLabel, severityToLabel, severityToColor, headerFieldLabels, headerFieldDescriptions, headerPolicyUrl } from './mappings';

// every header policy finding is reported as a warning: the header never blocks validation
const WARNING = 3;

// One row per finding. Reports validated before the policy emitted validation_details only
// carry the field names, so fall back to the stored field value as the observed value.
export function headerFindings(headerValidation) {
  if (!headerValidation) {
    return [];
  }
  const details = headerValidation.validation_details;
  if (Array.isArray(details) && details.length > 0) {
    return details;
  }
  return (headerValidation.validation_errors || []).map(field => ({
    field: field,
    expected: null,
    observed: field === 'description' ? headerValidation.mvd : headerValidation[field],
  }));
}

// group findings per header field, in File Info table order
function groupByField(findings) {
  const order = Object.keys(headerFieldLabels);
  const position = field => (order.includes(field) ? order.indexOf(field) : order.length);
  const groups = new Map();
  for (const finding of findings) {
    if (!groups.has(finding.field)) {
      groups.set(finding.field, []);
    }
    groups.get(finding.field).push(finding);
  }
  return [...groups.entries()].sort(([a], [b]) => position(a) - position(b));
}

function formatExpected(finding) {
  if (finding.expected) {
    return <i>{finding.expected}</i>;
  }
  return <a href={headerPolicyUrl(finding.field)} target="_blank" rel="noopener noreferrer">See header policy</a>;
}

function formatObserved(value) {
  if (value === null || value === undefined) {
    return <i>missing</i>;
  }
  const text = String(value);
  if (text.length === 0) {
    return <i>empty</i>;
  }
  // make leading/trailing whitespace visible, as the File Info table does
  const marked = text.replace(/^\s+|\s+$/g, match => '□'.repeat(match.length));
  return <span style={{ background: '#00000010', padding: '3px' }}>{marked}</span>;
}

export default function HeaderResult({ summary, status, headerValidation }) {
  const groups = groupByField(headerFindings(headerValidation));
  const panelStatus = groups.length > 0 ? 'w' : (status || 'p');

  return (
    <div>
      <TableContainer sx={{ maxWidth: 850 }} component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell colSpan={2} sx={{ borderColor: 'black', fontWeight: 'bold' }}>
                {summary}
              </TableCell>
            </TableRow>
          </TableHead>
        </Table>
      </TableContainer>

      <Paper sx={{overflow: 'hidden',
          "width": "850px",
          ".MuiTreeItem-root .MuiTreeItem-root": { backgroundColor: "#ffffff80", overflow: "hidden" },
          ".MuiTreeItem-group .MuiTreeItem-content": { boxSizing: "border-box" },
          ".MuiTreeItem-group": { padding: "16px", marginLeft: 0 },
          "> li > .MuiTreeItem-content": { padding: "16px" },
          ".MuiTreeItem-content.Mui-expanded": { borderBottom: 'solid 1px black' },
          ".MuiTreeItem-group .MuiTreeItem-content.Mui-expanded": { borderBottom: 0 },
          ".caption" : { paddingTop: "1em", paddingBottom: "1em" },
          ".caption-suffix" : { paddingTop: "1em", paddingBottom: "1em", fontSize: '0.9em', fontStyle: 'italic' },
          "table": { borderCollapse: 'collapse', fontSize: '80%' },
          "td, th": { padding: '0.2em 0.5em', verticalAlign: 'top' },
        }}
      >
        <div style={{ "backgroundColor": statusToColor[panelStatus], padding: '0.1em 0.0em' }}>
          { groups.length
            ? groups.map(([field, rows]) =>
                <TreeView
                  key={field}
                  defaultCollapseIcon={<ExpandMoreIcon />}
                  defaultExpandIcon={<ChevronRightIcon />}
                  defaultExpanded={[field]}
                >
                  <TreeItem
                    nodeId={field}
                    label={<div className='caption'>
                      {headerFieldLabels[field] || field} <span className='caption-suffix'>{rows.length > 1 ? `(occurred ${rows.length} times)` : ''}</span>
                    </div>}
                    sx={{ "backgroundColor": severityToColor[WARNING] }}
                  >
                    <div>
                      ⓘ {headerFieldDescriptions[field] || '-'}
                      <br />
                      <br />
                      <a target='blank' href={headerPolicyUrl(field)}>{headerPolicyUrl(field)}</a>
                      <br />
                      <br />
                    </div>
                    <table width='100%' style={{ textAlign: 'left' }}>
                      <thead>
                        <tr><th style={{ width: '10%' }}>Severity</th><th style={{ width: '45%' }}>Expected</th><th style={{ width: '45%' }}>Observed</th></tr>
                      </thead>
                      <tbody>
                        {rows.map((row, index) =>
                          <tr key={`${field}-${index}`}>
                            <td>{severityToLabel[WARNING]}</td>
                            <td>{formatExpected(row)}</td>
                            <td>{formatObserved(row.observed)}</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </TreeItem>
                </TreeView>
              )
            : <div style={{ margin: '0.5em 1em' }}>{statusToLabel[panelStatus]}</div> }
        </div>
      </Paper>
    </div>
  );
}
