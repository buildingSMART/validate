import * as React from 'react';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';
import statusToIcon from './mappings';


function prettyPrintFileSize(fileSizeInBytes) {
  var i = -1;
  var units = ['kB', 'MB', 'GB', 'TB'];
  do {
    fileSizeInBytes /= 1024;
    i++;
  } while (fileSizeInBytes > 1024);

  return Math.max(fileSizeInBytes, 0.01).toFixed(2) + ' ' + units[i];
}

function prettyPrintNumber(number) {
  if (number) {
    return number?.toLocaleString();
  }
  else {
    return '-';
  }
}

function preprocessData(data, type) {

  if (type === "general") {
    return [
      ["Report Date", data["model"]["date"]],
      ["File Name", data["model"]["filename"]],
      ["File Date", data["model"]["file_date"] !== null ? data["model"]["file_date"] : '-'],
      //["License", data["model"]["license"] !== null ? data["model"]["license"] : '-'],
      ["File Size", prettyPrintFileSize(data["model"]["size"])],
      ["Number of Geometries", prettyPrintNumber(data["model"]["number_of_geometries"])],
      ["Number of Properties", prettyPrintNumber(data["model"]["number_of_properties"])],
      ["IFC Schema", data["model"]["schema"] !== null ? data["model"]["schema"] : '-'],
      ["Authoring Application", data["model"]["authoring_application"] !== null ? data["model"]["authoring_application"] : '-'],
      ["MVD(s)", data["model"]["mvd"] !== null ? data["model"]["mvd"] : '-']
    ]

  } else {

    return [
      ["Syntax", statusToIcon[data["model"]["status_syntax"]]],
      ["Schema", statusToIcon[data["model"]["status_schema"]]],
      ["bSDD", statusToIcon[data["model"]["status_bsdd"]]],
      ["Prerequisites", statusToIcon[data["model"]["status_prereq"]]],
      ["Implementer Agreements", statusToIcon[data["model"]["status_ia"]]],
      ["Informal Propositions", statusToIcon[data["model"]["status_ip"]]],
      ["Industry Practices", statusToIcon[data["model"]["status_ind"]]],
    ]
  }

}


export default function GeneralTable({ data, type }) {
  const rows = preprocessData(data, type)

  return (
    <TableContainer sx={{ maxWidth: 850 }} component={Paper}>
      <Table aria-label="simple table">
        <TableHead>
          <TableRow>
            <TableCell colSpan={2} sx={{ borderColor: 'black', fontWeight: 'bold', textTransform: 'capitalize' }}>
              {type}
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow
              key={row[0]}
              sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
            >
              <TableCell sx={{width:'33%'}}>
                <b>{row[0]}</b>
              </TableCell>
              <TableCell align="left">{row[1]}</TableCell>

            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
