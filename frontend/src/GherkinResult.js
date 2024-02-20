import * as React from 'react';
import { TreeView, TreeItem } from '@mui/x-tree-view';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import Paper from '@mui/material/Paper';
import { statusToColor } from './mappings'

function GherkinResults({ status, gherkin_task }) {
    let label = "Rules"
    
    const messageToStatus = (msg) => {
        if (msg === "Rule passed" || msg === "Rule executed") {
            return "v";
        } else if (msg === "Rule disabled" || msg === "Rule not applicable") {
            return "n";
        } else {
            return "i";
        }
    };
    
    let previousStatus = null;
    
    return <Paper sx={{overflow: 'hidden'}}><TreeView
        aria-label="file system navigator"
        defaultCollapseIcon={<ExpandMoreIcon />}
        defaultExpandIcon={<ChevronRightIcon />}
        defaultExpanded={["0"]}
        sx={{ "width": "850px", "backgroundColor": statusToColor[status], ".MuiTreeItem-content": { padding: "16px" }, ".MuiTreeItem-content.Mui-expanded": { borderBottom: 'solid 1px black' } }}
    >
        { (gherkin_task && gherkin_task.results.length > 0) ?
        (<TreeItem nodeId="0" label={label}>
        {
            gherkin_task.results.map((result) => {
                const status = messageToStatus(result.message);
                const border = previousStatus !== null && previousStatus !== status
                    ? 'solid 1px gray'
                    : 'none';
                previousStatus = status;
                
                return (
                    <div style={{
                        backgroundColor: statusToColor[status],
                        marginLeft: '-17px',
                        paddingLeft: '17px',
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
            <pre>{gherkin_task ? "Valid" : "Not checked"}</pre>
        </TreeItem>) }
    </TreeView></Paper>
}


export default GherkinResults