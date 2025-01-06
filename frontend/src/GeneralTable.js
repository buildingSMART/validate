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
import WarningIcon from '@mui/icons-material/Warning';
import HourglassBottomIcon from '@mui/icons-material/HourglassBottom';

const statusToIcon = {
  "n": <BrowserNotSupportedIcon color="disabled" />,
  "v": <CheckCircleIcon color="success" />,
  "i": <ErrorIcon color="error" />,
  "w": <WarningIcon color="warning" />,
  "p": <HourglassBottomIcon color="disabled" />
}

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

  const BASE_LINK = "https://github.com/buildingSMART/IFC4.x-IF/tree/header-policy/docs/IFC-file-header#";

  const validationErrors = data["model"]["header_validation"]?.["validation_errors"] || [];

  function warningIconWithLink(field, path) {
    return (
      <>
        {field}
        <a href={`${BASE_LINK}${path}`} target="_blank" rel="noopener noreferrer">
          <WarningIcon color="warning" sx={{ marginLeft: 1 }} />
        </a>
      </>
    );
  }
  

  if (type === "general") {
    return [
      ["Report Date", data["model"]["date"]],
      ["IFC Schema", data["model"]["schema"] !== null ? data["model"]["schema"] : "-"],
      [
        <>
          MVD(s)
          {validationErrors.includes("description") &&
            warningIconWithLink("","description")}
        </>,
        data["model"]["header_validation"]?.["description"] || "-"
      ],
      [
        "File Name",
        data["model"]["header_validation"]?.["name"]
          ? data["model"]["header_validation"]["name"]
          : "-"
      ],
      ["File Size", prettyPrintFileSize(data["model"]["size"])],
      [
        <>
          File Date
          {validationErrors.includes("time_stamp") &&
            warningIconWithLink("","time_stamp")}
        </>,
        data["model"]["header_validation"]?.["time_stamp"] || "-"
      ],
      [
        <>
          Authoring Application
          {validationErrors.includes("originating_system") &&
            warningIconWithLink("","originating_system")}
        </>,
        data["model"]["header_validation"]?.["originating_system"] || "-"
      ],
      [
        <>
          Preprocessor Version
          {validationErrors.includes("preprocessor_version") &&
            warningIconWithLink("","preprocessor_version")}
        </>,
        data["model"]["header_validation"]?.["preprocessor_version"] || "-"
      ],
      [
        "Author",
        data["model"]["header_validation"]?.["author"]
          ? data["model"]["header_validation"]["author"]
          : "-"
      ],
      [
        <>
          Organization
          {validationErrors.includes("organization") &&
            warningIconWithLink("","organization")}
        </>,
        data["model"]["header_validation"]?.["organization"] || "-"
      ]
    ];
  } else {

    return [
      ["Syntax", statusToIcon[data["model"]["status_syntax"]]],
      ["Schema", statusToIcon[data["model"]["status_schema"]]],
      ["bSDD", statusToIcon[data["model"]["status_bsdd"]]],
      ["Prerequisites", statusToIcon[data["model"]["status_prereq"]]],
      ["Header", statusToIcon[data["model"]["status_header"]]],
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
