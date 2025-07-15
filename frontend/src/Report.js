import ResponsiveAppBar from './ResponsiveAppBar'
import Disclaimer from './Disclaimer';
import { useParams } from 'react-router-dom';

import Footer from './Footer';
import Grid from '@mui/material/Grid';
import GeneralTable from './GeneralTable';
import SyntaxResult from './SyntaxResult';
import SchemaResult from './SchemaResult';
import BsddTreeView from './BsddTreeView';
import GherkinResults from './GherkinResult';
import SideMenu from './SideMenu';
import FeedbackWidget from './FeedbackWidget';
import SelfDeclarationDialog from './SelfDeclarationDialog';

import SearchOffOutlinedIcon from '@mui/icons-material/SearchOffOutlined';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';

import { useEffect, useState, useContext } from 'react';
import { FETCH_PATH } from './environment'
import { PageContext } from './Page';
import HandleAsyncError from './HandleAsyncError';

function Report({ kind }) {
  const context = useContext(PageContext);

  const [isLoggedIn, setLogin] = useState(false);
  const [reportData, setReportData] = useState({});
  const [user, setUser] = useState(null);
  const [isLoaded, setLoadingStatus] = useState(false);
  const [errorStatus, setErrorStatus] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const { modelCode } = useParams()

  const [prTitle, setPrTitle] = useState("")
  const [commitId, setCommitId] = useState("")

  const handleAsyncError = HandleAsyncError();

  useEffect(() => {
    fetch(context.sandboxId ? `${FETCH_PATH}/api/sandbox/me/${context.sandboxId}` : `${FETCH_PATH}/api/me`, { credentials: 'include' })
      .then(response => response.json())
      .then((data) => {
        if (data["redirect"] !== undefined && data["redirect"] !== null) {
          if (!window.location.href.endsWith(data.redirect)) {
            window.location.href = data.redirect;
          }
        }
        else {
          setLogin(true);
          setUser(data["user_data"]);
          data["sandbox_info"]["pr_title"] && setPrTitle(data["sandbox_info"]["pr_title"]);
          data["sandbox_info"]["commit_id"] && setCommitId(data["sandbox_info"]["commit_id"]);
        }
      }).catch(handleAsyncError);
  }, [context, handleAsyncError]);


  function getReport(code, kind) {
    fetch(`${FETCH_PATH}/api/report/${code}?type=${kind}`)
      .then(response => {
        if (response.ok) {
          return response.json()
        } else if(response.status === 404) {
          return Promise.reject('Not Found')
        }
      })
      .then((data) => {
        setReportData(data);
        setErrorStatus(null);
        setErrorMessage(null);
        setLoadingStatus(true);
      })
      .catch((error) => {
        setErrorStatus(404);
        setErrorMessage(error)
        setLoadingStatus(true);
      });
  }


  useEffect(() => {
    getReport(modelCode, kind);
  }, [modelCode, kind]);

  if (isLoggedIn) {
    console.log("Report data ", reportData);
    const toTitle = s =>
      s.replace(/(^|_)([a-z])/g, (_, p1, p2) => (p1 ? ' ' : '') + p2.toUpperCase());
    function formatSignatureValue(v) {
      if (typeof v === 'string' && v.length > 64) {
        return v.substring(0, 61) + '...';
      } else {
        return v;
      }
    }
    return (
      <div>
        <Grid direction="column"
          container
          style={{
            minHeight: '100vh', alignItems: 'stretch',
          }} >
          <ResponsiveAppBar user={user} />
          <Grid
            container
            flex={1}
            direction="row"
            style={{
            }}
          >
            <SideMenu />

            <Grid
              container
              flex={1}
              direction="column"
              style={{
                justifyContent: "space-between",
                overflow: 'scroll',
                boxSizing: 'border-box',
                maxHeight: '90vh',
                overflowX: 'hidden'
              }}
            >
              <div style={{
                gap: '10px',
                flex: 1
              }}>
                <Grid
                  container
                  spacing={0}
                  direction="column"
                  alignItems="center"
                  justifyContent="space-between"
                  style={{
                    minHeight: '100vh', gap: '15px', backgroundColor: 'rgb(242 246 248)',
                    border: context.sandboxId ? 'solid 12px red' : 'none'
                  }}
                >
                  {context.sandboxId && <h2
                    style={{
                      background: "red",
                      color: "white",
                      marginTop: "-16px",
                      lineHeight: "30px",
                      padding: "12px",
                      borderRadius: "0 0 16px 16px"
                    }}
                  >Sandbox for <b>{prTitle}</b></h2>}
                  <Disclaimer />
                  {isLoaded && !errorStatus && 
                    <>
                        {(kind === "file") && <h2>File Info</h2>}
                        {(kind === "syntax") && <h2>STEP Syntax Report</h2>}
                        {(kind === "schema") && <h2>IFC Schema Report</h2>}
                        {(kind === "bsdd") && <h2>bSDD Compliance Report</h2>}
                        {(kind === "normative") && <h2>Normative IFC Rules Report</h2>}
                        {(kind === "industry") && <h2>Industry Practices Report</h2>}

                        <GeneralTable data={reportData} type={kind} />

                        {(kind === "syntax") && <SyntaxResult 
                          status={reportData.model.status_syntax} 
                          summary={"STEP Syntax"} 
                          content={reportData.results.syntax_results} />}

                        {(kind === "schema") && <SchemaResult 
                          status={reportData.model.status_schema} 
                          summary={"IFC Schema"} 
                          count={[...reportData.results.schema.counts, ...reportData.results.prereq_rules.counts]}
                          content={[...reportData.results.schema.results, ...reportData.results.prereq_rules.results]}
                          instances={reportData.instances} />}

                        {(kind === "bsdd") && <BsddTreeView 
                          status={reportData.model.status_bsdd} 
                          summary={"bSDD Compliance"} 
                          content={reportData.results.bsdd_results}
                          instances={reportData.instances} />}

                        {(kind === "normative") && <GherkinResults 
                          status={reportData.model.status_rules} 
                          summary={"Normative IFC Rules"}
                          count={reportData.results.norm_rules.counts}
                          content={reportData.results.norm_rules.results} 
                          instances={reportData.instances} />}
                          
                        {(kind === "industry") && <GherkinResults 
                          status={reportData.model.status_ind}
                          summary={"Industry Practices"}
                          count={reportData.results.ind_rules.counts}
                          content={reportData.results.ind_rules.results}
                          instances={reportData.instances} />}
                    </> }
                  {!isLoaded && <div>Loading...</div>}
                  {isLoaded && errorStatus && 
                    <div style={{ textAlign: "center" }}>
                      <h1>{errorStatus}</h1>
                      <h4>{errorMessage}</h4>
                      <SearchOffOutlinedIcon color="disabled" fontSize='large' />                      
                    </div>
                  }
                  {(kind === "file" && reportData && reportData.results && reportData.results.signatures) && 
                    <>
                      {(reportData.results.signatures.length > 0) && <h2 id="signatures">Digital signatures</h2>}
                      {reportData.results.signatures.map((sig, sigIndex) => (
                        <TableContainer sx={{ maxWidth: 850, border: `solid 2px ${sig.signature === 'invalid' ? 'red' : sig.signature === 'valid_unknown_cert' ? 'gray' : 'green'}` }} component={Paper}>
                          <Table aria-label="simple table">
                            <TableBody>
                              {["issuer", "subject", "signature_hash_algorithm_name", "rsa_key_size", "not_valid_after", "not_valid_before", "fingerprint_hex", "payload", "start", "end"].filter(x => sig[x]).map((item, itemIndex) =>
                                <TableRow key={`sig-${sigIndex}-${itemIndex}-key`} sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                                  <TableCell sx={{ width: '33%' }}>
                                    <b>{toTitle(item).replace('Rsa', 'RSA')}</b>
                                  </TableCell>
                                  <TableCell align="left">{formatSignatureValue(sig[item])}</TableCell>
                                </TableRow>
                              )}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      ))}
                    </>}
                  <Footer />
                </Grid>
              </div>
            </Grid>
          </Grid>

          <FeedbackWidget user={user} />
          <SelfDeclarationDialog user={user} />
          
        </Grid>
      </div>
    );
  }
}

export default Report;