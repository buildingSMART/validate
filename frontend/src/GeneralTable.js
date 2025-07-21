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
import Tooltip from '@mui/material/Tooltip';

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
  const validationErrors = data["model"]["header_validation"]?.["validation_errors"] || [];

  function warningIconWithLink(field, path) {
    const file_info_mapping = {
      "description": "One or more model view definitions used in the context of this data exchange.",
      "file_name": "The string of graphic characters used to name this particular instance of an exchange structure",
      "time_stamp": "The date and time specifying when the exchange structure was created, formatted in ISO 8601",
      "originating_system": "The software from which the model originated, also known as the authoring tool.",
      "preprocessor_version": "The system used to create the exchange structure, including the system product name and version.",
      "version": "The version of the model or file format used, derived from the originating system",
      "company_name": "The name of the company, derived from the originating system",
      "application_name": "The software used to export the model, derived from the originating system",
      "authorization": "The name and mailing address of the person who authorized the sending of the exchange structure.",
      "organization": "The group or organization with whom the author is associated.",
      "author": "The name and mailing address of the person responsible for creating the exchange structure.",
    };

    return (
      <>
        <Tooltip title={file_info_mapping[path] || "No description available"}>
          <span style={{ borderBottom: '1px dotted gray', cursor: 'help' }}>{field}</span>
        </Tooltip>
        {validationErrors.includes(path) && (
          <a
            href={`https://github.com/buildingSMART/IFC4.x-IF/tree/header-policy/docs/IFC-file-header#${path}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <WarningIcon color="warning" sx={{ marginLeft: 1 }} />
          </a>
        )}
      </>
    );
  }

  const rows = [
    ["Report Date", data["model"]["date"]],
    ["IFC Schema", data["model"]["header_validation"]?.["schema_identifier"] || "-"],
    [warningIconWithLink("MVD(s)", "description"), data["model"]["header_validation"]?.["description"] || "-"],
    [warningIconWithLink("File Name in Header", "file_name"), data["model"]["header_validation"]?.["name"] || "-"],
    ["File Name", data["model"]["filename"]],
    ["File Size", prettyPrintFileSize(data["model"]["size"])],
    [warningIconWithLink("File Date", "time_stamp"), data["model"]["header_validation"]?.["time_stamp"] || "-"],
  ];

  // return additional information for header validation report
  if (type === "file") {
    rows.push([warningIconWithLink("Originating System", "originating_system"), data["model"]["header_validation"]?.["originating_system"] || "-"]);
    rows.push([warningIconWithLink("Preprocessor Version", "preprocessor_version"), data["model"]["header_validation"]?.["preprocessor_version"] || "-"]);
    rows.push([warningIconWithLink("Company Name", "company_name"), data["model"]["header_validation"]?.["company_name"] || "-"]);
    rows.push([warningIconWithLink("Application Name", "application_name"), data["model"]["header_validation"]?.["application_name"] || "-"]);
    rows.push([warningIconWithLink("Application Version", "version"), data["model"]["header_validation"]?.["version"] || "-"]);
    rows.push([warningIconWithLink("Author", "author"), data["model"]["header_validation"]?.["author"] || "-"]);
    rows.push([warningIconWithLink("Organization", "organization"), data["model"]["header_validation"]?.["organization"] || "-"]);
  }

  return rows;
}

export default function GeneralTable({ data, type }) {
  const rows = preprocessData(data, type);

  console.log("Rows generated by preprocessData: ", rows);  // Debug to catch duplicates

  return (
    <TableContainer sx={{ maxWidth: 850 }} component={Paper}>
      <Table aria-label="simple table">
        <TableHead>
          <TableCell colSpan={2} sx={{ borderColor: 'black', fontWeight: 'bold' }}>
            {type.charAt(0).toUpperCase()}{type.slice(1)}
          </TableCell>
        </TableHead>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow key={`${row[0]}-${index}`} sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
              <TableCell sx={{ width: '33%' }}>
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

