import Dz from './Dz'
import ResponsiveAppBar from './ResponsiveAppBar'
import DashboardTable from './DashboardTable'
import Disclaimer from './Disclaimer';
import Footer from './Footer';
import FeedbackWidget from './FeedbackWidget';
import Grid from '@mui/material/Grid';
import VerticalLinearStepper from './VerticalLinearStepper'
import Button from '@mui/material/Button';
import HomeIcon from '@mui/icons-material/Home';
import CheckIcon from '@mui/icons-material/Check';
import Box from '@mui/material/Box';
import SideMenu from './SideMenu';
import Typography from '@mui/material/Typography';

import { useEffect, useState, useContext } from 'react';

import { FETCH_PATH } from './environment'
import { PageContext } from './Page';


function Dashboard() {
  const [isLoggedIn, setLogin] = useState(false);
  const [user, setUser] = useState(null);

  const [prTitle, setPrTitle] = useState("")

  const context = useContext(PageContext);

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
        }
      })
  }, []);

  document.body.style.overflow = "hidden";
  if (isLoggedIn) {
    return (
      <div class="dashboard">
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
                gap: '15px',
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

                  <Box sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    alignSelf: 'center',
                    paddingTop: '3em'
                  }}>
                    <Box
                      style={{
                        display: 'flex',
                        flexDirection: 'row',
                        alignItems: 'center',
                        marginLeft: '5px',
                        gap: '55px'
                      }}>
                      <Dz />
                      <VerticalLinearStepper />
                    </Box>
                  </Box>
                  <DashboardTable />
                  <Footer />
                </Grid>
              </div>
            </Grid>
          </Grid>

          <FeedbackWidget user={user} />

        </Grid>
      </div>
    );
  }
}

export default Dashboard;
