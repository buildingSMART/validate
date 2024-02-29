import * as React from 'react';
import { TreeView, TreeItem } from '@mui/x-tree-view';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import Paper from '@mui/material/Paper';
import { statusToColor } from './mappings'

function GherkinResults({ status, content }) {
    let label = "Rules"

    const severityToStatus = (severity) => {
        if (severity === 0) {
            return "n";  // n/a or disabled
        } else if (severity === 1 || severity === 2) {
            return "v"; // passed/executed
        } else if (severity === 3) {
            return "w"; // warning
        } else if (severity === 4) {
            return "i"; // failed/error
        }
    };
    
    let previousStatus = null;
    
    return (
      <Paper sx={{overflow: 'hidden'}}>
        <TreeView
            aria-label="report navigator"
            defaultCollapseIcon={<ExpandMoreIcon />}
            defaultExpandIcon={<ChevronRightIcon />}
            defaultExpanded={["0"]}
            sx={{ "width": "850px", "backgroundColor": statusToColor[status], ".MuiTreeItem-content": { padding: "16px" }, ".MuiTreeItem-content.Mui-expanded": { borderBottom: 'solid 1px black' } }}
        >
        { (content && content.length > 0) ?
        (<TreeItem nodeId="0" label={label}>
        {
            content.map((result) => {
                const status = severityToStatus(result.severity);
                const border = previousStatus !== null && previousStatus !== status
                    ? 'solid 1px gray'
                    : 'none';
                previousStatus = status;
                
                return (
                    <div style={{
                        backgroundColor: statusToColor[status],
                        marginLeft: '-17px',
                        paddingLeft: '17px',
                        paddingTop: '10px',
                        borderTop: border
                    }}>
                        <a href={result.feature_url}>{result.feature}</a> <br></br>
                        <b>{result.step}</b>
                        <div>outcome id: {result.id}</div>
                        <div>instance id: {result.instance_id ?? '-'}</div>
                        <div>message: {result.message}</div>
                        <br></br>
                        <br></br>
                    </div>
                )
            }
            )
        }
        </TreeItem>)
        : (<TreeItem nodeId="0" label={label}>
            <div style={{padding: '10px'}}>            
                {status === 'v' ? "Valid" : (status === 'i' ? "Invalid" : "Not checked")}
            </div>
        </TreeItem>) }
      </TreeView>
    </Paper>
   );
}

export default GherkinResults