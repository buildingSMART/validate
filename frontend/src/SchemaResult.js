import * as React from 'react';
import { useEffect, useState } from 'react';
import { TreeView, TreeItem } from '@mui/x-tree-view';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import Checkbox from "@mui/material/Checkbox";
import Tooltip from '@mui/material/Tooltip';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TablePagination from '@mui/material/TablePagination';
import { statusToColor, severityToColor, severityToLabel, statusToLabel } from './mappings';

function coerceToStr(v) {
  if (!v) {
    return '';
  }
  if (typeof v === 'string' || v instanceof String) {
    return v;
  }
  return JSON.stringify(v);
}

export default function SchemaResult({ summary, content, status, instances }) {
  const [data, setRows] = React.useState([])
  const [grouped, setGrouped] = useState([])
  const [page, setPage] = useState(0);  
  const [checked, setChecked] = useState(false);

  const handleChangePage = (_, newPage) => {
    setPage(newPage);
  };  

  const handleChangeChecked = (event) => {
    setChecked(event.target.checked);
    if (checked) {
      setPage(0);
    }
  };

  useEffect(() => {
    let grouped = [];
    let filteredContent = content.filter(function(el) {
      return checked || el.severity > 2; // all or warning/error only?
    });

    for (let c of (filteredContent || [])) {
      if (grouped.length === 0 || (c.attribute ? c.attribute : (c.feature ? 'Schema - Version' : 'Uncategorized')) !== grouped[grouped.length-1][0]) {
        grouped.push([c.attribute ? c.attribute : (c.feature ? 'Schema - Version' : 'Uncategorized'),[]])
      }
      grouped[grouped.length-1][1].push(c);
    }
    setRows(grouped.slice(page * 10, page * 10 + 10))
    setGrouped(grouped)
  }, [page, content, checked]);

  return (
    <div>
      <TableContainer sx={{ maxWidth: 850 }} component={Paper}>
        <Table>
          <TableHead>
            <TableCell colSpan={2} sx={{ borderColor: 'black', fontWeight: 'bold' }}>
              {summary}
            </TableCell>
            <TableCell sx={{ borderColor: 'black', fontSize: 'small', textAlign: 'right' }} >
              <Checkbox size='small'
                checked={checked}
                onChange={handleChangeChecked}
                tabIndex={-1}
                disableRipple
                color="default"
                label="test"
              />include Passed, Disabled and N/A &nbsp;
              <Tooltip title='This also shows Passed, Disabled and N/A rule results.'>
                <span style={{ display: 'inline-block'}}>
                  <span style={{fontSize: '.83em', verticalAlign: 'super'}}>ⓘ</span>
                </span>
              </Tooltip>
            </TableCell>
          </TableHead>
        </Table>
      </TableContainer>

      <Paper sx={{
          overflow: 'hidden',
            "width": "850px",
            "backgroundColor": statusToColor[status],
            ".MuiTreeItem-root .MuiTreeItem-root": { backgroundColor: "#ffffff80", overflow: "hidden" },
            ".MuiTreeItem-group .MuiTreeItem-content": { boxSizing: "border-box" },
            ".MuiTreeItem-group": { padding: "16px", marginLeft: 0 },
            "> li > .MuiTreeItem-content": { padding: "16px" },
            ".MuiTreeItem-content.Mui-expanded": { borderBottom: 'solid 1px black' },
            ".MuiTreeItem-group .MuiTreeItem-content.Mui-expanded": { borderBottom: 0 },
            ".caption" : { paddingTop: "1em", paddingBottom: "1em", textTransform: 'capitalize' },
            ".subcaption" : { visibility: "hidden", fontSize: '80%' },
            ".MuiTreeItem-content.Mui-expanded .subcaption" : { visibility: "visible" },
            "table": { borderCollapse: 'collapse', fontSize: '80%' },
            "td, th": { padding: '0.2em 0.5em', verticalAlign: 'top' },
            ".pre": {
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              // overflowWrap: 'break-word'
            }
          }}>
          <div >
            { data.length
              ? data.map(([hd, rows]) => {
                  return <TreeView 
                    defaultCollapseIcon={<ExpandMoreIcon />}
                    defaultExpandIcon={<ChevronRightIcon />}
                    >
                      <TreeItem nodeId={hd} label={<div><div class='caption'>{(rows[0].constraint_type || '').replace('_', ' ')}{rows[0].constraint_type && ' - '}{hd}</div><div class='subcaption'>{rows[0].constraint_type !== 'schema' ? (coerceToStr(rows[0].msg)).split('\n')[0] : ''}</div></div>}
                        sx={{ "backgroundColor": severityToColor[rows[0].severity] }}
                      >

                      <table width='100%' style={{ 'text-align': 'left'}}>
                          <thead>
                            <tr><th>Id</th><th>Entity</th><th>Severity</th><th>Message</th></tr>
                          </thead>
                          <tbody>
                          {rows.map((row, rowIndex) => {
                              const featureDescription = row.feature ? row.feature.replace(/^IFC\d{3}\s*-\s*/, '') : '';

                              return (
                                <tr key={rowIndex}>
                                  <td>{instances[row.instance_id] ? instances[row.instance_id].guid : '-'}</td>
                                  <td>{instances[row.instance_id] ? instances[row.instance_id].type : '-'}</td>
                                  <td>{severityToLabel[row.severity]}</td>
                                  <td>
                                    <span className='pre'>
                                      {featureDescription && row.expected && row.observed 
                                        ? `Description: ${featureDescription} ,  Expected: ${coerceToStr(row.expected)}, Observed: ${coerceToStr(row.observed)}`
                                        : (
                                            row.feature
                                              ? `${featureDescription}\n${coerceToStr(row.msg)}`
                                              : (row.constraint_type !== 'schema'
                                                  ? coerceToStr(row.msg).split('\n').slice(2).join('\n')
                                                  : coerceToStr(row.msg))
                                          )
                                      }
                                    </span>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </TreeItem>
                    </TreeView>
                })
                : <div style={{ margin: '0.5em 1em' }}>{statusToLabel[status]}</div> }
            {
              grouped.length && grouped.length > 0
              ? <TablePagination
                  sx={{display: 'flex', justifyContent: 'center', backgroundColor: statusToColor[status]}}
                  rowsPerPageOptions={[10]}
                  component="div"
                  count={grouped.length}
                  rowsPerPage={10}
                  page={page}
                  onPageChange={handleChangePage}
                />
              : null
            }
          </div>
        
      </Paper>
    </div>
  );
}