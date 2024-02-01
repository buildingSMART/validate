import * as React from 'react';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';
import ErrorIcon from '@mui/icons-material/Error';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import BrowserNotSupportedIcon from '@mui/icons-material/BrowserNotSupported';
import WarningIcon from '@mui/icons-material/Warning'


const statusToIcon = {
  "n": <BrowserNotSupportedIcon color="disabled" />,
  "v": <CheckCircleIcon color="success" />,
  "i": <ErrorIcon color="error" />,
  "w": <WarningIcon color="warning" />
}
function preprocessData(data, type) {

  if (type == "general") {
    return [
      ["Date", data["model"]["date"]],
      ["File name", data["model"]["filename"]],
      ["License", data["model"]["license"]],
      ["File size", data["model"]["size"]],
      ["Number of geometries", data["model"]["number_of_geometries"]],
      ["Number of properties", data["model"]["number_of_properties"]],
      ["IFC Schema", data["model"]["schema"]],
      ["Authoring Application", data["model"]["authoring_application"]],
      ["MVD(s)", data["model"]["mvd"]]
    ]

  } else {

    return [
      ["Syntax", statusToIcon[data["model"]["status_syntax"]]],
      ["Schema", statusToIcon[data["model"]["status_schema"]]],
      ["bSDD", statusToIcon[data["model"]["status_bsdd"]]],
      ["Implementer Agreements", statusToIcon[data["model"]["status_ia"]]],
      ["Informal Propositions", statusToIcon[data["model"]["status_ip"]]],
    ]
  }

}


export default function GeneralTable({ data, type }) {
  const rows = preprocessData(data, type)

  return (
    <TableContainer sx={{ maxWidth: 850 }} component={Paper}>
      <Table aria-label="simple table">
        <TableHead>
          <TableCell colSpan={2} sx={{ borderColor: 'black', fontWeight: 'bold' }}>
            {type.charAt(0).toUpperCase()}{type.slice(1)}
          </TableCell>
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
