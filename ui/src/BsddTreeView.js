import * as React from 'react';
import TreeView from '@mui/lab/TreeView';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import TreeItem from '@mui/lab/TreeItem';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';
import { statusToColor } from './mappings'


function BsddReportRow({ key, valid, instance, requirement, required, observed }) {
  return (
    <TableRow
      key={key}
      sx={{ '&:last-child td, &:last-child th': { border: 0 }, "backgroundColor": (valid == 1) ? statusToColor['v'] : statusToColor['i'] }}
    >
      <TableCell align="center" component="th" scope="row">
        {`${instance}`}
      </TableCell>
      <TableCell align="center"> {`${requirement}`}</TableCell>
      <TableCell align="center"> {`${required}`}</TableCell>
      <TableCell align="center">  {`${observed}`}</TableCell>
    </TableRow>

  )

}

export default function BsddTreeView({ bsddResults, status }) {

  const bsdd = bsddResults.bsdd;

  return (
    <Paper sx={{ overflow: 'hidden' }}><TreeView
      aria-label="file system navigator"
      defaultCollapseIcon={<ExpandMoreIcon />}
      defaultExpandIcon={<ChevronRightIcon />}
      defaultExpanded={["0"]}
      sx={{ "width": "850px", "backgroundColor": statusToColor[status], "> li > .MuiTreeItem-content": { padding: "16px" }, ".MuiTreeItem-content.Mui-expanded": { borderBottom: 'solid 1px black' } }}
    >
      <TreeItem nodeId="0" label={"bSDD"}>
        <TreeView defaultCollapseIcon={<ExpandMoreIcon />}
          defaultExpandIcon={<ChevronRightIcon />}>
          {
            Object.entries(bsdd).map(([domain, classifications]) => {

              return <TreeItem nodeId={11} label={`Domain: ${domain}`} disabled={domain == "no IfcClassification" ? true : false}>
                <TreeView defaultCollapseIcon={<ExpandMoreIcon />}
                  defaultExpandIcon={<ChevronRightIcon />}>
                  {
                    Object.entries(classifications).map(([classification, results]) => {
                      return <TreeItem nodeId={12} label={`Classification: ${classification}`} disabled={classification == "no IfcClassificationReference" ? true : false}>
                        {
                          results.map((result) => {
                            return <div >
                              <br></br>
                              {
                                (domain != "no IfcClassification" && classification != "no IfcClassificationReference") &&
                                <TableContainer sx={{
                                  minWidth: 650,
                                  "width": "90%",
                                  "padding": "10px"
                                }} >
                                  <Table sx={{
                                    minWidth: 650,
                                    "backgroundColor": "rgb(238, 238, 238)",
                                  }}
                                    size="small"
                                    aria-label="a dense table">
                                    <TableHead>
                                      <TableRow>
                                        <TableCell align="center">Instance</TableCell>
                                        <TableCell align="center">Requirement</TableCell>
                                        <TableCell align="center">Required</TableCell>
                                        <TableCell align="center">Observed</TableCell>

                                      </TableRow>
                                    </TableHead>
                                    <TableBody>

                                      {/* IFC TYPE */}
                                      <BsddReportRow valid={result.val_ifc_type}
                                        key={"0"}
                                        instance={result.global_id}
                                        requirement={"IFC entity type"}
                                        required={result.bsdd_type_constraint}
                                        observed={result.ifc_type}
                                      />

                                      {/* PROPERTY SET  */}
                                      <BsddReportRow valid={result.val_property_set}
                                        key={"1"}
                                        instance={result.global_id}
                                        requirement={"Property Set"}
                                        required={result.bsdd_property_constraint.propertySet}
                                        observed={result.ifc_property_set}
                                      />

                                      {/* PROPERTY */}
                                      <BsddReportRow valid={result.val_property_name}
                                        key={"2"}
                                        instance={result.global_id}
                                        requirement={"Property Name"}
                                        required={result.bsdd_property_constraint.name}
                                        observed={result.ifc_property_value}
                                      />

                                      {/* DATA TYPE */}
                                      <BsddReportRow valid={result.val_property_type}
                                        key={"3"}
                                        instance={result.global_id}
                                        requirement={"Property Value Type"}
                                        required={result.bsdd_property_constraint.dataType}
                                        observed={result.ifc_property_type}
                                      />

                                      {/* PROPERTY VALUE */}
                                      <BsddReportRow valid={result.val_property_value}
                                        key={"4"}
                                        instance={result.global_id}
                                        requirement={"Property Value"}
                                        required={result.bsdd_property_constraint.predefinedValue}
                                        observed={result.ifc_property_value}
                                      />
                                    </TableBody>
                                  </Table>
                                </TableContainer>
                              }

                            </div>
                          }
                          )
                        }
                      </TreeItem>
                    }
                    )
                  }
                </TreeView>
              </TreeItem>
            })
          }
        </TreeView>
      </TreeItem>
    </TreeView></Paper>
  );
}