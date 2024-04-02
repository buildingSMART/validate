import * as React from 'react';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TablePagination from '@mui/material/TablePagination';
import { useEffect, useState } from 'react';
import { statusToColor, severityToLabel, statusToLabel } from './mappings';

export default function SyntaxResult({ summary, content, status }) {
  const [rows, setRows] = React.useState([])
  const [page, setPage] = useState(0);

  const handleChangePage = (_, newPage) => {
    setPage(newPage);
  };  

  useEffect(() => {
    setRows(content.slice(page * 10, page * 10 + 10))
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
            ".MuiTreeItem-root .MuiTreeItem-root": { backgroundColor: "#ffffff80", overflow: "hidden" },
            ".MuiTreeItem-group .MuiTreeItem-content": { boxSizing: "border-box" },
            ".MuiTreeItem-group": { padding: "16px", marginLeft: 0 },
            "> li > .MuiTreeItem-content": { padding: "16px" },
            ".MuiTreeItem-content.Mui-expanded": { borderBottom: 'solid 1px black' },
            ".MuiTreeItem-group .MuiTreeItem-content.Mui-expanded": { borderBottom: 0 },
            ".caption" : { paddingTop: "1em", paddingBottom: "1em", textTransform: 'capitalize' },
            ".subcaption" : { visibility: "hidden", fontSize: '80%' },
            ".MuiTreeItem-content.Mui-expanded .subcaption" : { visibility: "visible" },
            "table": { borderCollapse: 'collapse', fontSize: '80%'},
            "td, th": { padding: '0.2em 0.5em', verticalAlign: 'top' },
            ".pre": {
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              // overflowWrap: 'break-word'
            },
            ".mono": { fontFamily: 'monospace, monospace', marginTop: '0.3em' }
          }}>

        <div style={{ "backgroundColor": statusToColor[status], padding: '0.1em 0.0em' }}>
          { rows.length
              ? rows.map(item => {
                  return <table width='100%' style={{ 'text-align': 'left', margin: '0.8em 0.8em'}}>
                          <thead >
                            <tr><th>Line</th><th>Column</th><th>Severity</th><th>Message</th></tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td>{item.lineno}</td>
                              <td>{item.column}</td>
                              <td>{severityToLabel[item.severity]}</td>
                              <td>
                                <span class='pre'>{item.msg.split('\n').slice(0, -2).join('\n')}</span>
                                <span class='pre mono'>{item.msg.split('\n').slice(-2).join('\n')}</span>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                })
              : <div style={{ margin: '0.5em 1em' }}>{statusToLabel[status]}</div> }
            {
              content.length && content.length > 0
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