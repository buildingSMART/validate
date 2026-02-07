import * as React from 'react';
import { useEffect, useState } from 'react';
import { TreeView, TreeItem } from '@mui/x-tree-view';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import Checkbox from "@mui/material/Checkbox";
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import IconButton from '@mui/material/IconButton';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TablePagination from '@mui/material/TablePagination';
import Tooltip from '@mui/material/Tooltip';
import { statusToColor, severityToLabel, statusToLabel, severityToColor } from './mappings';

function unsafe_format(obj) {
  // PJS003 -> Invalid characters in GUID
  if (typeof obj == 'object' && 'invalid_guid_chars' in obj && 'expected_or_observed' in obj) {
    if (obj.expected_or_observed === 'expected') {
      return <span>{`One of the following characters: ${obj.invalid_guid_chars}`}</span>;
    } else if (obj.expected_or_observed === 'observed' && 'inst' in obj) {
      return (
        <span>
          {`For guid '${obj.inst}', the following invalid character(s) is/were found: ${obj.invalid_guid_chars}`}
        </span>
      );
    }
  }

    // PJS003 -> invalid length
    if (typeof obj == 'object' && 'length' in obj && 'expected_or_observed' in obj) {
      if (obj.expected_or_observed === 'expected') {
        return <span>{`A sequence of length ${obj.length} for the global ID`}</span>;
      } else if (obj.expected_or_observed === 'observed' && 'inst' in obj) {
        return <span>{`The guid '${obj.inst}' is a sequence of length ${obj.length}`}</span>;
      }
    }

  if (typeof obj == 'object' && 'value' in obj) {
    if (typeof obj.value === 'string' || obj.value instanceof String || typeof obj.value === 'number' || typeof obj.value === 'boolean') {
      return <span style={{background: '#00000010', padding: '3px'}}>{obj.value}</span>
    } else {
      return unsafe_format(obj.value);
    }
  } else if (typeof obj === 'string' || obj instanceof String) {
    return <i>{obj}</i>;
  } else if (typeof obj == 'object' && 'instance' in obj) {
    return <span style={{padding: '3px', borderBottom: 'dotted 3px gray'}}>{obj.instance}</span>
  } else if (typeof obj == 'object' && 'entity' in obj) {
    var entity = obj.entity.split('(#')[0];
    return <a href={`https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/${entity}.htm`}>{entity}</a>
  } else if (typeof obj == 'object' && 'oneOf' in obj) {
    let ctx = obj.context ? `${obj.context.charAt(0).toUpperCase()}${obj.context.slice(1)} one of:` : `One of:`;
    return <div>{ctx}<div></div><ul>{obj.oneOf.map(v => <li>{v}</li>)}</ul></div>;
  } else if (typeof obj == 'object' && 'schema_identifier' in obj) {
    let lines = obj.schema_identifier.split("\n");
    return <div>{lines ? lines.map(line => <div> {line} </div>) : obj.schema_identifier}</div>;
  } else if (typeof obj == 'object' && 'num_digits' in obj) {
    // Custom formatting for calculated alignment consistency
    let ctx = obj.context ? `${obj.context.charAt(0).toUpperCase()}${obj.context.slice(1)} :` : `One of:`;

    let reported_value = obj.expected || obj.observed;
    let display_value;
    if ( Array.isArray(reported_value) ) {
      display_value = reported_value;
    } else {
      display_value = reported_value.toExponential(obj.num_digits);
    }

    let directionLabel;
    if (ctx.includes('direction')) {
      directionLabel = 'Tangent Direction';
    }
    else if (ctx.includes('gradient'))  {
      directionLabel = 'Gradient';
    }
    else {
      // warning is raised for position, so don't report any details of direction or gradient
      directionLabel= 'suppress';
    }

    if ('continuity_details' in obj) {
      let dts = obj.continuity_details;
      return (
        <div>
          <div>{ctx} {display_value}</div>
          <div>at end of {dts.segment_to_analyze}</div>
          <ul>Coords: ({dts.current_end_point[0]}, {dts.current_end_point[1]})</ul>
          { directionLabel !== 'suppress' && (
            <ul>{directionLabel}: {dts.current_end_direction}</ul>) }
          <br />
          <div>and start of {dts.following_segment}</div>
          <ul>Coords: ({dts.following_start_point[0]}, {dts.following_start_point[1]})</ul>
          { directionLabel !== 'suppress' && (
          <ul>{directionLabel}: {dts.following_start_direction}</ul> )}
        </div>
      );
    } else {
      if (ctx === 'Position :') {
        let msg = `${ctx} (${display_value[0]}, ${display_value[1]})`;
        return <div>{msg}</div>;
      } else {
        return <div>{ctx} {display_value}</div>;
      }
    }

  } else {
    return JSON.stringify(obj);
  }
}

function format(obj) {
  try {
    return unsafe_format(obj);
  } catch {
    return JSON.stringify(obj);
  }
}

// helper function to extract plain text from formatted data
function extractPlainText(obj) {
  if (typeof obj === 'string') return obj;
  if (typeof obj === 'number' || typeof obj === 'boolean') return String(obj);
  if (typeof obj === 'object' && obj !== null) {
    if ('value' in obj) return extractPlainText(obj.value);
    if ('instance' in obj) return obj.instance;
    if ('entity' in obj) return obj.entity.split('(#')[0];
    if ('oneOf' in obj) return obj.oneOf.join(', ');
    if ('schema_identifier' in obj) return obj.schema_identifier;
  }
  return JSON.stringify(obj);
}

export default function GherkinResult({ summary, count, content, status, instances }) {
  const [data, setRows] = useState([])
  const [grouped, setGrouped] = useState([])
  const [page, setPage] = useState(0);
  const [checked, setChecked] = useState(false);
  const [copyStatus, setCopyStatus] = useState({});

  const handleChangePage = (_, newPage) => {
    setPage(newPage);
  };

  const handleChangeChecked = (event) => {
    setChecked(event.target.checked);
    if (checked) {
      setPage(0);
    }
  };

  const copyTableToClipboard = async (feature, rows) => {
    const hasMessage = rows.some(row => row.message && row.message.length > 0);
    let text = `${feature}\n\n`;
    text += `Severity\tId\tEntity\tExpected\tObserved${hasMessage ? `\tMessage` : ''}\n`;

    rows.forEach(row => {
      const severity = severityToLabel[row.severity] || '';
      const id = row.instance_id ? (instances[row.instance_id]?.guid || '?') : '-';
      const entity = row.instance_id ? (instances[row.instance_id]?.type || '?') : '-';
      const expected = row.expected ? extractPlainText(row.expected) : '-';
      const observed = row.observed ? extractPlainText(row.observed) : '-';
      const message = hasMessage ? (row.message || '-') : '';

      text += `${severity}\t${id}\t${entity}\t${expected}\t${observed}${hasMessage ? `\t${message}` : ''}\n`
    });

    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus({...copyStatus, [feature]: 'success'});
      setTimeout(() => {
        setCopyStatus(prev => ({...prev, [feature]: null}));
      }, 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
      setCopyStatus({...copyStatus, [feature]: 'error'});
      setTimeout(() => {
        setCopyStatus(prev => ({...prev, [feature]: null}));
      }, 2000);
    }
  };

  useEffect(() => {
    let grouped = [];
    let filteredContent = content.filter(function(el) {
      return checked || el.severity > 2; // all or warning/error only?
    });

    // only keep visible columns
    filteredContent = filteredContent.map(function(el) {
      const container = {};

      container['instance_id'] = el.instance_id ? el.instance_id : '-';
      container.feature = el.feature;
      container.feature_version = el.feature_version;
      container.feature_url = el.feature_url;
      container.feature_text = el.feature_text;
      container.observed = el.observed ? el.observed : '-';
      container.expected = el.expected ? el.expected : '-';
      container.severity = el.severity;
      container.msg = el.msg;
      container.title = el.title;

      return container
    })

    // // deduplicate
    // const uniqueArray = (array, key) => {

    //   return [
    //     ...new Map(
    //       array.map( x => [key(x), x])
    //     ).values()
    //   ]
    // }

    // filteredContent = uniqueArray(filteredContent, c => c.instance_id + c.feature + c.severity);

    // sort
    filteredContent.sort((f1, f2) => f1.feature > f2.feature ? 1 : -1);

    for (let c of (filteredContent || [])) {
      if (grouped.length === 0 || (c.title) !== grouped[grouped.length-1][0]) {
        grouped.push([c.title,[]])
      }
      grouped[grouped.length-1][1].push(c);
    }

    // aggregate severity
    for (let g of (grouped || [])) {
      g[2] = Math.max(...g[1].map(f => f.severity))
    }

    // order features
    grouped.sort((f1, f2) => f1[0] > f2[0] ? 1 : -1);

    setRows(grouped.slice(page * 10, page * 10 + 10))
    setGrouped(grouped)
  }, [page, content, checked]);

  function partialResultsOnly(rows) {
    return count[rows[0].title] > rows.length;
  }

  function getTitleSuffix(rows) {
    let occurrences = count[rows[0].title];
    let times = (occurrences > 1) ? ' times' : ' time';
    const warning_or_error = (rows[0].severity >= 3);
    return warning_or_error ? '(occurred ' + occurrences.toLocaleString() + times + ')' : '';
  }

  return (
    <div>
      <TableContainer sx={{ maxWidth: 850 }} component={Paper}>
        <Table>
          <TableHead>
            <TableCell sx={{ borderColor: 'black', fontWeight: 'bold' }}>
              {summary}
            </TableCell>
            <TableCell sx={{ borderColor: 'black', fontSize: 'small', textAlign: 'right' }} >
              <Checkbox size='small'
                checked={checked}
                onChange={handleChangeChecked}
                tabIndex={-1}
                disableRipple
                color="default"
                label="test"
              />include Passed, Disabled and N/A &nbsp;
              <Tooltip title='This also shows Passed, Disabled and N/A rule results.'>
                <span style={{ display: 'inline-block'}}>
                  <span style={{fontSize: '.83em', verticalAlign: 'super'}}>ⓘ</span>
                </span>
              </Tooltip>
            </TableCell>
          </TableHead>
        </Table>
      </TableContainer>

    <Paper sx={{overflow: 'hidden',
          "width": "850px",
          ".MuiTreeItem-root .MuiTreeItem-root": { backgroundColor: "#ffffff80", overflow: "hidden" },
          ".MuiTreeItem-group .MuiTreeItem-content": { boxSizing: "border-box" },
          ".MuiTreeItem-group": { padding: "16px", marginLeft: 0 },
          "> li > .MuiTreeItem-content": { padding: "16px" },
          ".MuiTreeItem-content.Mui-expanded": { borderBottom: 'solid 1px black' },
          ".MuiTreeItem-group .MuiTreeItem-content.Mui-expanded": { borderBottom: 0 },
          ".caption" : { paddingTop: "1em", paddingBottom: "1em", textTransform: 'capitalize' },
          ".caption-suffix" : { paddingTop: "1em", paddingBottom: "1em", fontSize: '0.9em', textTransform: 'none', fontStyle: 'italic' },
          ".subcaption" : { visibility: "hidden", fontSize: '80%' },
          ".MuiTreeItem-content.Mui-expanded .subcaption" : { visibility: "visible" },
          "table": { borderCollapse: 'collapse', fontSize: '80%' },
          "td, th": { padding: '0.2em 0.5em', verticalAlign: 'top' },
          "td ul": { paddingLeft: '2em' },
          ".pre": {
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            // overflowWrap: 'break-word'
          },
          ".mono": { fontFamily: 'monospace, monospace', marginTop: '0.3em' }
        }}
      >
        <div style={{ "backgroundColor": statusToColor[status], padding: '0.1em 0.0em' }}>
          { data.length
            ? data.map(([feature, rows, severity]) => {
                const hasMessage = rows.some(row => row.message && row.message.length > 0)
                return <TreeView
                  defaultCollapseIcon={<ExpandMoreIcon />}
                  defaultExpandIcon={<ChevronRightIcon />}
                  >
                    <TreeItem
                      nodeId={feature}
                      label={<div>
                        <div class='caption'>
                          {feature} <span class='caption-suffix'>{getTitleSuffix(rows)}</span>
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              copyTableToClipboard(feature, rows).then();
                            }}
                            sx={{ ml: 1}}
                            title={copyStatus[feature] === 'success' ? 'Copied!' : 'Copy to clipboard'}
                            color={copyStatus[feature] === 'success' ? 'success' : 'default'}
                            >
                              <ContentCopyIcon fontsize="small" />
                            </IconButton>
                          </div>
                        </div>}
                      sx={{ "backgroundColor": severityToColor[severity] }}
                    >
                      <div>
                        ⓘ {rows[0].feature_text !== null ? rows[0].feature_text : '-'}
                        <br />
                        <br />
                        <a size='small' target='blank' href={rows[0].feature_url}>{rows[0].feature_url}</a>
                        <br />
                        <br />
                        { partialResultsOnly(rows) &&
                          <div>
                            ⓘ Note: a high number of occurrences were identified. Only the first {rows.length.toLocaleString()} occurrences are displayed below.
                            <br />
                            <br />
                          </div>
                        }
                      </div>
                      <table width='100%' style={{ 'text-align': 'left'}}>
                        <thead>
                          <tr><th>Severity</th><th>Id</th><th>Entity</th><th>Expected</th><th>Observed</th>{hasMessage && <th>Message</th>}</tr>
                        </thead>
                        <tbody>
                          {
                            rows.map((row) => {
                              return <tr>
                                <td>{severityToLabel[row.severity]}</td>
                                <td>{row.instance_id ? (instances[row.instance_id] ? instances[row.instance_id].guid : '?') : '-'}</td>
                                <td>{row.instance_id ? (instances[row.instance_id] ? instances[row.instance_id].type : '?') : '-'}</td>
                                <td>{row.expected ? format(row.expected) : '-'}</td>
                                <td>{row.observed ? format(row.observed) : '-'}</td>
                                {hasMessage && <td>{row.message && row.message.length > 0 ? row.message : '-'}</td>}
                            </tr>
                            })
                          }
                        </tbody>
                      </table>
                    </TreeItem>
                  </TreeView>
              })
            : <div style={{ margin: '0.5em 1em' }}>{statusToLabel[status]}</div> }
          {
            grouped.length && grouped.length > 0
            ? <TablePagination
                sx={{display: 'flex', justifyContent: 'center'}}
                rowsPerPageOptions={[10]}
                component="div"
                count={grouped.length}
                rowsPerPage={10}
                page={page}
                onPageChange={handleChangePage}
              />
            : null
          }
        </div>
    </Paper>
    </div>
  );
}
