import * as React from 'react';
import { useEffect, useState } from 'react';
import { TreeView, TreeItem } from '@mui/x-tree-view';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableBody from '@mui/material/TableBody';
import TableRow from '@mui/material/TableRow';
import TablePagination from '@mui/material/TablePagination';
import Box from '@mui/material/Box';
import { statusToColor, severityToLabel, statusToLabel } from './mappings';

export default function SchemaResult({ summary, content, status, instances }) {
  const [data, setRows] = React.useState([])
  const [page, setPage] = useState(0);

  const handleChangePage = (_, newPage) => {
    setPage(newPage);
  };  

  useEffect(() => {
    let grouped = [];
    for (let c of (content || []).slice(page * 10, page * 10 + 10)) {
      if (grouped.length === 0 || (c.attribute ? c.attribute : (c.feature ? 'Schema version' : 'Uncategorized')) !== grouped[grouped.length-1][0]) {
        grouped.push([c.attribute ? c.attribute : (c.feature ? 'Schema version' : 'Uncategorized'),[]])
      }
      grouped[grouped.length-1][1].push(c);
    }
    setRows(grouped)
  }, [page, content]);

  return (
    <div>
      <TableContainer sx={{ maxWidth: 850 }} component={Paper}>
        <Table>
          <TableHead>
            <TableCell colSpan={2} sx={{ borderColor: 'black', fontWeight: 'bold' }}>
              {summary}
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
                      <TreeItem nodeId={hd} label={<div><div class='caption'>{(rows[0].constraint_type || '').replace('_', ' ')}{rows[0].constraint_type && ' - '}{hd}</div><div class='subcaption'>{rows[0].constraint_type !== 'schema' ? (rows[0].msg || '').split('\n')[0] : '\u00A0'}</div></div>}>

                      <table width='100%' style={{ 'text-align': 'left'}}>
                          <thead>
                            <tr><th>Id</th><th>Entity</th><th>Severity</th><th>Message</th></tr>
                          </thead>
                          <tbody>
                            {
                              rows.map((row) => {
                                return <tr>
                                  <td>{instances[row.instance_id] ? instances[row.instance_id].guid : '?'}</td>
                                  <td>{instances[row.instance_id] ? instances[row.instance_id].type : '?'}</td>
                                  <td>{severityToLabel[row.severity]}</td>
                                  <td><span class='pre'>{
                                    row.feature
                                      ? `${row.feature}\n${row.message}`
                                      : (row.constraint_type !== 'schema'
                                          ? row.msg.split('\n').slice(2).join('\n')
                                          : row.msg)
                                  }</span></td>                              </tr>
                              })
                            }
                          </tbody>
                        </table>
                      </TreeItem>
                    </TreeView>
                })
                : <div style={{ margin: '0.5em 1em' }}>{statusToLabel[status]}</div> }
            {
              content.length
              ? <TablePagination
                  sx={{display: 'flex', justifyContent: 'center', backgroundColor: statusToColor[status]}}
                  rowsPerPageOptions={[10]}
                  component="div"
                  count={content.length}
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