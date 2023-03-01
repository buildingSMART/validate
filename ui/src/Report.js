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

import { useEffect, useState, useContext } from 'react';
import { FETCH_PATH } from './environment'
import { PageContext } from './Page';

function Report() {

  const context = useContext(PageContext);

  const [isLoggedIn, setLogin] = useState(false);
  const [reportData, setReportData] = useState({});
  const [user, setUser] = useState(null)
  const [isLoaded, setLoadingStatus] = useState(false)

  const { modelCode } = useParams()

  const [prTitle, setPrTitle] = useState("")
  const [commitId, setCommitId] = useState("")

  useEffect(() => {
    fetch(context.sandboxId?`${FETCH_PATH}/api/sandbox/me/${context.sandboxId}`:`${FETCH_PATH}/api/me`)
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
        <Grid
          container
          spacing={0}
          direction="column"
          alignItems="center"
          justifyContent="space-between"
          style={{ minHeight: '100vh', gap: '15px', backgroundColor: 'rgb(238, 238, 238)', border: context.sandboxId?'solid 12px red':'none'}}
        >
          <ResponsiveAppBar user={user} />
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

          <h2>Validation Report</h2>

          <GeneralTable data={reportData} type={"general"} />
          <GeneralTable data={reportData} type={"overview"} />

          <SyntaxResult status={reportData["model"]["status_syntax"]} content={reportData["results"]["syntax_result"]} />
          <SchemaResult status={reportData["model"]["status_schema"]} content={reportData["results"]["schema_result"]} instances={reportData.instances} />

          <BsddTreeView status={reportData["model"]["status_bsdd"]} summary={"bSDD"} bsddResults={reportData["results"]["bsdd_results"]} />

          <GherkinResults status={reportData["model"]["status_ia"]} gherkin_task={reportData.tasks["implementer_agreements_task"]} task_type="implementer_agreements_task" />
          <GherkinResults status={reportData["model"]["status_ip"]} gherkin_task={reportData.tasks["informal_propositions_task"]} task_type="informal_propositions_task" />
          <Footer />
        </Grid>
      </div>
    );
  }
}

export default Report;
