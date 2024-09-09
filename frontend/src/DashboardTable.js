import * as React from 'react';
import PropTypes from 'prop-types';
import { alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TablePagination from '@mui/material/TablePagination';
import TableRow from '@mui/material/TableRow';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Checkbox from '@mui/material/Checkbox';
import IconButton from '@mui/material/IconButton';
import InfoIcon from '@mui/icons-material/Info';
import Tooltip from '@mui/material/Tooltip';
import DeleteIcon from '@mui/icons-material/Delete';
//import ReplayIcon from '@mui/icons-material/Replay';
import CircularStatic from "./CircularStatic";
import ErrorIcon from '@mui/icons-material/Error';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import BrowserNotSupportedIcon from '@mui/icons-material/BrowserNotSupported';
import WarningIcon from '@mui/icons-material/Warning';
import HourglassBottomIcon from '@mui/icons-material/HourglassBottom';
import BlockIcon from '@mui/icons-material/Block';
import Link from '@mui/material/Link';
import { FETCH_PATH } from './environment'
import { useEffect, useState, useContext } from 'react';
import { PageContext } from './Page';
import HandleAsyncError from './HandleAsyncError';
import { getCookieValue } from './Cookies';

const statusToIcon = {
  "n": <BrowserNotSupportedIcon color="disabled" />,
  "v": <CheckCircleIcon sx={{ color: "#2ab672" }} />,
  "i": <ErrorIcon color="error" />,
  "w": <WarningIcon color="warning" />,
  "p": <HourglassBottomIcon color="disabled" />,
  "-": <Tooltip title='N/A'><BlockIcon color="disabled" /></Tooltip>,
  "info":<InfoIcon color="primary"/>
}

function wrap_status(status, href) {
  if (status === 'n' || status === 'p' || status === '-') {
    return statusToIcon[status];
  } else {
    return <IconButton component={Link} href={href} target="_blank" onClick={evt => evt.stopPropagation()}>
      {statusToIcon[status]}
    </IconButton>;
  }
}

function computeRelativeDates(modelDate) {
  var offset = modelDate.getTimezoneOffset();
  modelDate = new Date(
    Date.UTC(
      modelDate.getUTCFullYear(),
      modelDate.getUTCMonth(),
      modelDate.getUTCDate(),
      modelDate.getUTCHours(),
      modelDate.getUTCMinutes() - offset,
      modelDate.getUTCSeconds()
    )
  );

  var now = new Date();
  var difference = (now - modelDate) / 1000; // convert from ms to s
  let divisor, unit;
  try {
    [divisor, unit] = [[3600 * 24 * 8, null], [3600 * 24 * 7, "weeks"], [3600 * 24, "days"], [3600, "hours"], [60, "minutes"], [1, "seconds"]].filter(a => difference / a[0] > 1.)[0];
  } catch {
    return ''
  }
  if (unit) {
    var relativeTime = Math.floor(difference / divisor);
    if (relativeTime == 1) { unit = unit.slice(0, -1); } // Remove the 's' in units if only 1
    return (<span className="abs_time" title={modelDate.toLocaleString()}>{relativeTime} {unit} ago</span>)
  } else {
    return modelDate.toLocaleString();
  }
}

const headCells = [
  {
    id: 'filename',
    label: 'File Name',
  },
  {
    id: 'syntax',
    label: 'STEP Syntax',
    width: 100,
    align: 'center',
    tooltip: 'STEP Physical File Syntax'
  },
  {
    id: 'schema',
    label: 'IFC Schema',
    width: 100,
    align: 'center',
    tooltip: 'IFC Schema: inverse attributes, attribute types, cardinalities, where rules, function constraints'
  },
  {
    id: 'rules',
    label: 'Normative IFC Rules',
    width: 100,
    align: 'center',
    tooltip: 'Implementer Agreements and Informal Propositions'
  },
  {
    id: 'industry',
    label: 'Industry Practices',
    width: 100,
    align: 'center',
    tooltip: 'Checking the IFC file against common practice and sensible defaults. None of these checks render the IFC file invalid'
  },
  // disabled bSDD
  // {
  //   id: 'bsdd',
  //   label: 'bSDD Compliance',
  //   width: 100,
  //   align: 'center'
  // },
  {
    id: 'date',
    label: 'Date',
  },
  {
    id: 'download',
    label: '',
  }
];

function EnhancedTableHead(props) {
  const { onSelectAllClick, order, orderBy, numSelected, rowCount, onRequestSort } =
    props;

  return (
    <TableHead>
      <TableRow style={{ backgroundColor: '#e4eaee' }}>
        <TableCell padding="checkbox">
          <Checkbox
            color="primary"
            indeterminate={numSelected > 0 && numSelected < rowCount}
            checked={rowCount > 0 && numSelected === rowCount}
            onChange={onSelectAllClick}
            inputProps={{
              'aria-label': '',
            }}
          />
        </TableCell>
        {headCells.map((headCell) => (
          <TableCell
            key={headCell.id}
            align={headCell.align || 'left'}
            padding='normal'
            width={headCell.width}
            sx={{fontWeight: 'bold'}}
          >
            {
              headCell.tooltip
                ? <Tooltip title={headCell.tooltip}>
                    <span style={{borderBottom: 'dotted 2px gray', display: 'inline-block'}}>{headCell.label}
                      <span style={{fontSize: '.83em', verticalAlign: 'super'}}>{headCell.tooltip ? 'ⓘ' : ''}</span>
                    </span>
                  </Tooltip>
                : headCell.label
            }
          </TableCell>
        ))}
      </TableRow>
    </TableHead>
  );
}

EnhancedTableHead.propTypes = {
  numSelected: PropTypes.number.isRequired,
  onSelectAllClick: PropTypes.func.isRequired,
  rowCount: PropTypes.number.isRequired,
};

function EnhancedTableToolbar({ numSelected, onDelete, onRevalidate }) {

  return (
    <Toolbar
      sx={{
        pl: { sm: 1 },
        pr: { xs: 1, sm: 1 },
        backgroundColor: "none",
        ...(numSelected > 0 && {
          bgcolor: (theme) =>
            alpha(theme.palette.primary.main, theme.palette.action.activatedOpacity),
        }),
      }}
    >
      {numSelected > 0 && (
        <Tooltip title="Delete">
          <IconButton onClick={onDelete}>
            <DeleteIcon />
          </IconButton>
        </Tooltip>)}

      {/* {numSelected > 0 && (
        <Tooltip title="Revalidate">
          <IconButton onClick={onRevalidate}>
            <ReplayIcon />
          </IconButton>
        </Tooltip>)} */}

      {numSelected > 0 ? (
        <Typography
          //sx={{ flex: '1 1 100%' }}
          color="inherit"
          variant="subtitle1"
          component="div"
        >
          {numSelected} selected
        </Typography>
      ) : (
        <Typography
          // sx={{ flex: '1 1 100%' }}
          variant="h6"
          id="tableTitle"
          component="div"
        />
      )}
      
    </Toolbar>
  );
}

EnhancedTableToolbar.propTypes = {
  numSelected: PropTypes.number.isRequired,
};

export default function DashboardTable({ models }) {
  const [rows, setRows] = React.useState([])
  const [order, setOrder] = React.useState('asc');
  const [orderBy, setOrderBy] = React.useState('');
  const [selected, setSelected] = React.useState([]);
  const [page, setPage] = React.useState(0);
  const [dense, setDense] = React.useState(false);
  const [rowsPerPage, setRowsPerPage] = React.useState(5);
  const [count, setCount] = React.useState(0);
  const [deleted, setDeleted] = useState('');
  const [revalidated, setRevalidated] = useState('');
  const [progress, setProgress] = useState(0);

  const context = useContext(PageContext);
  const handleAsyncError = HandleAsyncError();

  useEffect(() => {
    fetch(`${FETCH_PATH}/api/models_paginated/${page * rowsPerPage}/${page * rowsPerPage + rowsPerPage}`)
      .then((response) => response.json())
      .then((json) => {
        setRows(json["models"]);
        setCount(json["count"]);
        if (json.models.some(m => (m.progress < 100))) {
          setTimeout(() => {setProgress(progress + 1)}, 5000)
        }
      }).catch(handleAsyncError);
  }, [page, rowsPerPage, progress, deleted, handleAsyncError]);


  const handleSelectAllClick = (event) => {
    if (event.target.checked) {
      const newSelected = rows.map((n) => n.id);
      setSelected(newSelected);
      return;
    }
    setSelected([]);
  };

  const handleClick = (event, filename) => {
    const selectedIndex = selected.indexOf(filename);
    let newSelected = [];

    if (selectedIndex === -1) {
      newSelected = newSelected.concat(selected, filename);
    } else if (selectedIndex === 0) {
      newSelected = newSelected.concat(selected.slice(1));
    } else if (selectedIndex === selected.length - 1) {
      newSelected = newSelected.concat(selected.slice(0, -1));
    } else if (selectedIndex > 0) {
      newSelected = newSelected.concat(
        selected.slice(0, selectedIndex),
        selected.slice(selectedIndex + 1),
      );
    }

    setSelected(newSelected);
  };

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const isSelected = (name) => selected.indexOf(name) !== -1;

  // Avoid a layout jump when reaching the last page with empty rows.
  const emptyRows =
    page > 0 ? Math.max(0, (1 + page) * rowsPerPage - rows.length) : 0;

  useEffect(() => {
    if (deleted) {
      fetch(`${FETCH_PATH}/api/delete/${deleted}`, {
        method: 'DELETE',
        headers: { 'x-csrf-token': getCookieValue('csrftoken') },
        credentials: 'include'
      })
        .then((response) => response.json())
        .then((json) => {
          setSelected([])
          setDeleted([])
        });
    } else if (revalidated) {
      fetch(`${FETCH_PATH}/api/revalidate/${revalidated}`, {
        method: 'POST',
        headers: { 'x-csrf-token': getCookieValue('csrftoken') },
        credential: 'include'
      })
        .then((response) => response.json())
        .then((json) => {
          setSelected([])
          setRevalidated([])
        });   
    }

  }, [deleted, revalidated]);

  function onDelete() {
    setDeleted(selected.join(','))
  }

  // function onRevalidate() {
  //   setRevalidated(selected.join(','))
  // }

  return (
    <Box sx={{ width: '100%', alignSelf: 'start' }}>

      {/* <EnhancedTableToolbar numSelected={selected.length} onDelete={onDelete} onRevalidate={onRevalidate} /> */}
      <EnhancedTableToolbar numSelected={selected.length} onDelete={onDelete} />
      <TableContainer>
        <Table
          sx={{ 
            backgroundColor: 'white',
            '.MuiIconButton-root' : {
              // border: 'solid 1px rgba(0,0,0,30%)',
              boxShadow: '2px 2px 3px rgba(0,0,0,10%)'
            },
            '.MuiIconButton-root:hover' : {
              // border: 'solid 1px rgba(0,0,0,30%)',
              boxShadow: '2px 2px 3px rgba(0,0,0,30%)'
            },
            '*' : {
              lineHeight: '1em'
            }
          }}
          aria-labelledby="tableTitle"
          size={dense ? 'small' : 'medium'}
        >
          <EnhancedTableHead
            numSelected={selected.length}
            onSelectAllClick={handleSelectAllClick}
            rowCount={rows.length}
          />
          <TableBody>
            {rows.map((row, index) => {
              const isItemSelected = isSelected(row.id);
              const labelId = `enhanced-table-checkbox-${index}`;
              return (
                <TableRow
                  hover
                  onClick={(event) => handleClick(event, row.id)}
                  role="checkbox"
                  aria-checked={isItemSelected}
                  tabIndex={-1}
                  key={row.id}
                  selected={isItemSelected}
                >
                  <TableCell padding="checkbox">
                    <Checkbox
                      color="primary"
                      checked={isItemSelected}
                      inputProps={{
                        'aria-labelledby': labelId,
                      }}
                    />
                  </TableCell>
                  <TableCell align="left">{row.filename} {wrap_status("info", context.sandboxId ? `/sandbox/report_file/${context.sandboxId}/${row.code}` : `/report_file/${row.code}`)}</TableCell>
                  <TableCell align="center">
                    {wrap_status(row.status_syntax, context.sandboxId ? `/sandbox/report_syntax/${context.sandboxId}/${row.code}` : `/report_syntax/${row.code}`)}
                  </TableCell>
                  <TableCell align="center">
                    {wrap_status(row.status_schema, context.sandboxId ? `/sandbox/report_schema/${context.sandboxId}/${row.code}` : `/report_schema/${row.code}`)}
                  </TableCell>
                  <TableCell align="center">
                    {wrap_status(row.status_rules, context.sandboxId ? `/sandbox/report_rules/${context.sandboxId}/${row.code}` : `/report_rules/${row.code}`)}
                  </TableCell>
                  <TableCell align="center">
                    {wrap_status(row.status_ind, context.sandboxId ? `/sandbox/report_industry/${context.sandboxId}/${row.code}` : `/report_industry/${row.code}`)}
                  </TableCell>
                  {/* <TableCell align="center">
                    {wrap_status(row.status_bsdd, context.sandboxId ? `/sandbox/report_bsdd/${context.sandboxId}/${row.code}` : `/report_bsdd/${row.code}`)}
                  </TableCell> */}
                
                  {
                    // (row.progress == 100) ?
                    // <TableCell align="left">
                    //   <Link href={context.sandboxId ? `/sandbox/report/${context.sandboxId}/${row.code}` : `/report/${row.code}`} underline="hover">
                    //     {'View report'}
                    //   </Link>
                    // </TableCell> :
                    // <TableCell align="left"></TableCell>

                  }

                  {
                    (row.progress == 100) ?
                      <TableCell align="left">{computeRelativeDates(new Date(row.date))}</TableCell> :
                      <TableCell align="left">
                        {
                          (row.progress == -1) ? <Typography>{"in queue"}</Typography> :
                            ((row.progress == -2) ? <Typography>{"an error occured"}</Typography> : <CircularStatic value={row.progress} />)
                        }
                      </TableCell>
                  }

                  <TableCell align="left">
                    <Link href={`${FETCH_PATH}/api/download/${row.id}`} underline="hover" onClick={evt => evt.stopPropagation()}>
                      {'Download file'}
                    </Link>
                  </TableCell>
                </TableRow>
              );

            })}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        rowsPerPageOptions={[5, 10, 25]}
        component="div"
        count={count}
        rowsPerPage={rowsPerPage}
        page={page}
        onPageChange={handleChangePage}
        onRowsPerPageChange={(event) => { setRowsPerPage(parseInt(event.target.value, 10)) }}
      />

    </Box>
  );
}