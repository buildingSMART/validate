import ResponsiveAppBar from './ResponsiveAppBar'
import Disclaimer from './Disclaimer';
import { useParams } from 'react-router-dom';

import Footer from './Footer';
import Grid from '@mui/material/Grid';
import GeneralTable from './GeneralTable';
import SyntaxResult from './SyntaxResult';
import SchemaResult from './SchemaResult';
import BsddTreeView from './BsddTreeView'
import GherkinResults from './GherkinResult';
import SideMenu from './SideMenu';

import { useEffect, useState, useContext } from 'react';
import { FETCH_PATH } from './environment';
import { PageContext } from './Page';
import HandleAsyncError from './HandleAsyncError';

function Report({ kind }) {
  const context = useContext(PageContext);

  const [isLoggedIn, setLogin] = useState(false);
  const [reportData, setReportData] = useState({});
  const [user, setUser] = useState(null)
  const [isLoaded, setLoadingStatus] = useState(false)

  const { modelCode } = useParams()

  const [prTitle, setPrTitle] = useState("")
  const [commitId, setCommitId] = useState("")

  const handleAsyncError = HandleAsyncError();

  useEffect(() => {
    fetch(context.sandboxId ? `${FETCH_PATH}/api/sandbox/me/${context.sandboxId}` : `${FETCH_PATH}/api/me`)
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


  function getReport(code) {
    fetch(`${FETCH_PATH}/api/report2/${code}`)
      .then(response => response.json())
      .then((data) => {
        setReportData(data);
        setLoadingStatus(true);
      })
  }

  useEffect(() => {
    getReport(modelCode);
  }, [modelCode]);

  if (isLoggedIn) {
    console.log("Report data ", reportData);
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
                  {isLoaded
                    ? <>
                        {(kind === "syntax") && <h2>Syntax Report</h2>}
                        {(kind === "schema") && <h2>Schema Report</h2>}
                        {(kind === "bsdd") && <h2>bSDD Report</h2>}
                        {(kind === "rules") && <h2>Rules Report</h2>}
                        {(kind === "file") && <h2>File metrics</h2>}
                        {(kind === "industry") && <h2>Industry Practices Report</h2>}

                        <GeneralTable data={reportData} type={"general"} />

                        <b><font color='red'>-- NOTE: Work In Progress --</font></b>

                        {(kind === "syntax") && <SyntaxResult status={reportData.model.status_syntax} summary={"Syntax"} content={reportData.results.syntax_result} />}
                        {(kind === "schema") && <SchemaResult status={reportData.model.status_schema} summary={"Schema"} content={[...reportData.results.schema_result, ...reportData.tasks.prerequisites_validation_task.results]} instances={reportData.instances} />}
                        {(kind === "bsdd") && <BsddTreeView status={reportData.model.status_bsdd} summary={"bSDD"} bsddResults={reportData.results.bsdd_results} />}
                        {(kind === "rules") && <GherkinResults status={reportData.model.status_ia} gherkin_task={reportData.tasks.gherkin_rules_validation_task} />}
                        {(kind === "industry") && <GherkinResults status={reportData.model.status_ind} gherkin_task={reportData.tasks.industry_practices_validation_task} />}
                      </>
                    : <div>Loading...</div>}
                  <Footer />
                </Grid>
              </div>
            </Grid>
          </Grid>
        </Grid>
      </div>
    );
  }
}

export default Report;