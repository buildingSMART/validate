import './App.css';
import Dz from './Dz'
import ResponsiveAppBar from './ResponsiveAppBar'
import Disclaimer from './Disclaimer';
import Footer from './Footer'
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import SideMenu from './SideMenu';
import VerticalLinearStepper from './VerticalLinearStepper'

import { useEffect, useState } from 'react';
import { FETCH_PATH } from './environment'

import {PageContext} from './Page';
import { useContext } from 'react';
import { Typography } from '@mui/material';

function App() {

  const context = useContext(PageContext);

  const [isLoggedIn, setLogin] = useState(false);
  const [user, setUser] = useState(null)

  const [prTitle, setPrTitle] = useState("")
 
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
        }
      })
  }, []);

  document.body.style.overflow = "hidden";
  if (isLoggedIn) {
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
                    
                  <div style={{alignSelf:"start", marginLeft:"5px"}}>
                    <Typography variant="h6" >What is the Validation Service?</Typography>
                    <Typography  align='left' paragraph>
                      The Validation Service enables to upload IFC files to check them against different specifications and provide meaningful output results to the user.
                    </Typography>
                  </div>

                  <div style={{alignSelf:"start", marginLeft:"5px"}}>
                    <Typography variant="h6" >What does it check?</Typography>
                    <Typography  align='left' paragraph>
                    The Validation Service checks IFC files against the STEP Syntax, the IFC Schema, constraining rules and the bSDD.
                    </Typography>
                  </div>
                
                  <Box sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    alignSelf: 'normal',
                    width: '100%'
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

export default App;
