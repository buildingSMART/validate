import * as React from 'react';
import TreeView from '@mui/lab/TreeView';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import TreeItem from '@mui/lab/TreeItem';
import { statusToColor } from './mappings'
import Paper from '@mui/material/Paper';

export default function MinimalTreeView({ summary, content, status }) {
  return (
    <Paper sx={{overflow: 'hidden'}}>
      <TreeView
        aria-label="file system navigator"
        defaultCollapseIcon={<ExpandMoreIcon />}
        defaultExpandIcon={<ChevronRightIcon />}
        defaultExpanded={["0"]}
        sx={{ "width": "850px", "backgroundColor": statusToColor[status], ".MuiTreeItem-content": { padding: "16px" }, ".MuiTreeItem-content.Mui-expanded": { borderBottom: 'solid 1px black' } }}
      >
        <TreeItem nodeId="0" label={summary}>
          <pre>{content}</pre>
        </TreeItem>
      </TreeView>
    </Paper>
  );
}