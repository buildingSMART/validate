import * as React from 'react';
import TreeView from '@mui/lab/TreeView';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import TreeItem from '@mui/lab/TreeItem';
import { statusToColor } from './mappings'
import Paper from '@mui/material/Paper';

export default function SyntaxResult({ content, status }) {
  return (
    <Paper sx={{overflow: 'hidden'}}>
      <TreeView
        aria-label="file system navigator"
        defaultCollapseIcon={<ExpandMoreIcon />}
        defaultExpandIcon={<ChevronRightIcon />}
        defaultExpanded={["0"]}
        sx={{
          "width": "850px",
          "backgroundColor": statusToColor[status],
          ".MuiTreeItem-root .MuiTreeItem-root": { backgroundColor: "#ffffff80", overflow: "hidden" },
          ".MuiTreeItem-group .MuiTreeItem-content": { boxSizing: "border-box" },
          ".MuiTreeItem-group": { padding: "16px", marginLeft: 0 },
          "> li > .MuiTreeItem-content": { padding: "16px" },
          ".MuiTreeItem-content.Mui-expanded": { borderBottom: 'solid 1px black' },
          ".MuiTreeItem-group .MuiTreeItem-content.Mui-expanded": { borderBottom: 0 },
          ".caption" : { textTransform: 'capitalize' },
          ".subcaption" : { visibility: "hidden", fontSize: '80%' },
          ".MuiTreeItem-content.Mui-expanded .subcaption" : { visibility: "visible" },
          "table": { borderCollapse: 'collapse', fontSize: '80%' },
          "td, th": { padding: '0.2em 0.5em', verticalAlign: 'top' },
          ".pre": { whiteSpace: 'pre', display: 'block' },
          ".mono": { fontFamily: 'monospace, monospace', marginTop: '0.3em' }
        }}
      >
        <TreeItem nodeId="0" label="Syntax">
        { content.length
            ? content.map(item => {
                return <TreeView defaultCollapseIcon={<ExpandMoreIcon />}
                  defaultExpandIcon={<ChevronRightIcon />}>
                    <TreeItem nodeId="syntax-0" label={<div class='caption'>{(item.error_type || 'syntax_error').replace('_', ' ')}</div>}>
                      <table>
                        <thead>
                          <tr><th>Line</th><th>Column</th><th>Message</th></tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>{item.lineno}</td>
                            <td>{item.column}</td>
                            <td>
                              <span class='pre'>{item.msg.split('\n').slice(0, -2).join('\n')}</span>
                              <span class='pre mono'>{item.msg.split('\n').slice(-2).join('\n')}</span>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </TreeItem>
                  </TreeView>
              })
            : <div>{content ? "Valid" : "Not checked"}</div> }
          </TreeItem>
      </TreeView>
    </Paper>
  );
}