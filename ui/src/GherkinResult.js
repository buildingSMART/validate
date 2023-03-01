import * as React from 'react';
import TreeView from '@mui/lab/TreeView';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import TreeItem from '@mui/lab/TreeItem';
import Paper from '@mui/material/Paper';
import { statusToColor } from './mappings'

function GherkinResults({ status, gherkin_task, task_type }) {
    let label = task_type==="implementer_agreements_task"?"Implementer Agreements":"Informal Propositions";
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

                return (
                    <div>
                        <a href={result.feature_url}>{result.feature}</a> <br></br>
                        <b>{result.step}</b>
                        <div>{result.message}</div>
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