import ResponsiveAppBar from './ResponsiveAppBar'
import Disclaimer from './Disclaimer';
import { useParams } from 'react-router-dom'

import Footer from './Footer'
import Grid from '@mui/material/Grid';
import GeneralTable from './GeneralTable';
import SyntaxResult from './SyntaxResult.js'
import SchemaResult from './SchemaResult';
import BsddTreeView from './BsddTreeView'
import GherkinResults from './GherkinResult';
import SideMenu from './SideMenu';

import { useEffect, useState, useContext } from 'react';
import { FETCH_PATH } from './environment'
import { PageContext } from './Page';

function Report({ kind }) {
  const context = useContext(PageContext);

  const [isLoggedIn, setLogin] = useState(false);
  const [reportData, setReportData] = useState({});
  const [user, setUser] = useState(null)
  const [isLoaded, setLoadingStatus] = useState(false)

  const { modelCode } = useParams()

  const [prTitle, setPrTitle] = useState("")
  const [commitId, setCommitId] = useState("")

  useEffect(() => {
    fetch(context.sandboxId ? `${FETCH_PATH}/api/sandbox/me/${context.sandboxId}` : `${FETCH_PATH}/api/me`)
      .then(response => response.json())
      .then((data) => {
        if (data["redirect"] !== undefined) {
          window.location.href = data.redirect;
        }
        else {
          setLogin(true);
          setUser(data["user_data"]);
          data["sandbox_info"]["pr_title"] && setPrTitle(data["sandbox_info"]["pr_title"]);
          data["sandbox_info"]["commit_id"] && setCommitId(data["sandbox_info"]["commit_id"]);
        }
      })
  }, []);


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
  }, []);

  if (isLoggedIn && isLoaded) {
    console.log("Report data ", reportData)
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

                  {
                    (kind === "syntax_and_schema")
                    && <h2>Syntax and Schema Report</h2>
                  }
                  {
                    (kind === "bsdd")
                    && <h2>bSDD Report</h2>
                  }
                  {
                    (kind === "rules")
                    && <h2> Rules Report</h2>
                  }

                  <GeneralTable data={reportData} type={"general"} />
                
                  {
                    (kind === "syntax_and_schema")
                      ? <SyntaxResult status={reportData["model"]["status_syntax"]} summary={"Syntax"} content={reportData["results"]["syntax_result"]} />
                      : null
                  }
                  {
                    (kind === "syntax_and_schema")
                      ? <SchemaResult status={reportData["model"]["status_schema"]} summary={"Schema"} content={reportData["results"]["schema_result"]} instances={reportData.instances} />
                      : null
                  }
                  {
                    (kind === "bsdd")
                      ? <BsddTreeView status={reportData["model"]["status_bsdd"]} summary={"bSDD"} bsddResults={reportData["results"]["bsdd_results"]} />
                      : null
                  }
                  {
                    (kind === "rules")
                      ? <GherkinResults status={reportData["model"]["status_ia"]} gherkin_task={reportData.tasks["implementer_agreements_task"]} task_type="implementer_agreements_task" />
                      : null
                  }
                  {
                    (kind === "rules")
                      ? <GherkinResults status={reportData["model"]["status_ip"]} gherkin_task={reportData.tasks["informal_propositions_task"]} task_type="informal_propositions_task" />
                      : null
                  }

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