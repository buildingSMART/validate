import { Link, Typography } from '@mui/material';

import Dz from './Dz'
import ResponsiveAppBar from './ResponsiveAppBar'
import Footer from './Footer'
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import SideMenu from './SideMenu';
import VerticalLinearStepper from './VerticalLinearStepper'
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';

import FeedbackWidget from './FeedbackWidget';
import SelfDeclarationDialog from './SelfDeclarationDialog';

import { useEffect, useState, useContext } from 'react';
import { PageContext } from './Page';
import { FETCH_PATH } from './environment';
import { getCookieValue } from './Cookies';

import {
  Accordion,
  AccordionSummary,
  AccordionDetails
} from "@mui/material";

import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";
import DataObjectOutlinedIcon from "@mui/icons-material/DataObjectOutlined";
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import CheckOutlinedIcon from "@mui/icons-material/CheckOutlined";
import StarOutlineOutlinedIcon from "@mui/icons-material/StarOutlineOutlined";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";

import './App.css';

const items = [
  {
    icon: DataObjectOutlinedIcon,
    title: "STEP Syntax",
    desc: "Confirms the uploaded file is a valid STEP Physical File (SPF) in accordance with ISO 10303-21.",
  },
  {
    icon: DescriptionOutlinedIcon,
    title: "IFC Schema",
    desc: "Checks against the referenced IFC schema version, including formal propositions and EXPRESS-encoded functions.",
  },
  {
    icon: CheckOutlinedIcon,
    title: "Normative Rules",
    desc: "Validates implementer agreements and informal propositions defined in the IFC specification.",
  },
  {
    icon: StarOutlineOutlinedIcon,
    title: "Industry Practices",
    desc: "Non-normative checks against common practices and sensible defaults used across the industry.",
  },
];

const steps = [
  { n: "01", title: "Upload", desc: "Upload your .ifc file (256mb max)" },
  { n: "02", title: "Validate", desc: "Automated checks run against the IFC standard" },
  { n: "03", title: "Review", desc: "Get a detailed conformity report with errors and warnings" },
];

const faqs = [
  {
    q: "Is the Validation Service free?",
    a: "Yes. The service is free and provided by buildingSMART international to improve interoperability of IFC.",
  },
  {
    q: "Do I need an account?",
    a: "Yes. An account is required for progress notifications and to gather statistics on authoring tools; developer accounts are excluded from these statistics.",
  },
  {
    q: "Does it include geometric visualisation?",
    a: "The emphasis is on the four validation layers outlined above, while there are rules that relate to geometry there is no geometric visualization of the model or coordination features."
  },
  {
    q: "What IFC schema versions are supported?",
    a: "The supported schemas are IFC2X3, IFC4 and IFC 4.3 (IFC4X3_ADD2)",
  },
];

const resources = [
  {
    kicker: "buildingSMART",
    title: "About buildingSMART",
    desc: "In-depth information on everything we do at buildingSMART.org",
    href: "https://buildingsmart.org",
  },
  {
    kicker: "Docs",
    title: "User Guide & Documentation",
    desc: "Step-by-step guide and technical reference",
    href: "https://buildingsmart.github.io/validate/index.html",
  },
  {
    kicker: "GitHub",
    title: "Source Code on GitHub",
    desc: "Open-source repository - run it on your own infrastructure",
    href: "https://github.com/buildingSMART/validate",
  },
  {
    kicker: "Forum",
    title: "Community Forum",
    desc: "Updates, discussions, and feedback",
    href: "https://forums.buildingsmart.org/",
  },
];

function App() {

  const context = useContext(PageContext);

  const [isLoggedIn, setLogin] = useState(false);
  const [user, setUser] = useState(null);

  const [prTitle, setPrTitle] = useState("")

  useEffect(() => {
    fetch(context.sandboxId ? `${FETCH_PATH}/api/sandbox/me/${context.sandboxId}` : `${FETCH_PATH}/api/me`, { credentials: 'include', 'x-csrf-token': getCookieValue('csrftoken') })
      .then(response => response.json())
      .then((data) => {
        if (data["redirect"] === undefined || data["redirect"] === null) {
          setLogin(true);
          setUser(data["user_data"]);
          data["sandbox_info"]["pr_title"] && setPrTitle(data["sandbox_info"]["pr_title"]);
        }
      })
  }, []);

  document.body.style.overflow = "hidden";
  return (
    <div class="home">
      <Grid direction="column"
        container
        style={{
          minHeight: '100vh', alignItems: 'stretch',
        }} >
        <ResponsiveAppBar user={isLoggedIn ? user : null}></ResponsiveAppBar>
        <Grid
          container
          flex={1}
          direction="row"
          style={{
          }}
        >
          {isLoggedIn && <SideMenu />}

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
                  minHeight: '100vh',
                  background: `url(${require('./background.jpg')}) fixed`,
                  backgroundSize: 'cover',
                  border: context.sandboxId ? 'solid 12px red' : 'none',
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

                <Box sx={{
                  width: '100%',
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'rgba(0,0,0,0.30)',
                  padding: '5em 2em',
                  boxSizing: 'border-box',
                }}>
                  <Container maxWidth="md" sx={{ textAlign: 'center', color: '#fff' }}>
                    <Typography variant="h3" sx={{ fontWeight: 700, mb: 2, textShadow: '0 2px 8px rgba(0,0,0,0.5)' }}>
                      IFC Validation Service
                    </Typography>
                    <Typography variant="h6" sx={{ mb: 4, fontWeight: 400, textShadow: '0 1px 4px rgba(0,0,0,0.6)' }}>
                      A free, open platform by buildingSMART for checking IFC file conformity against STEP syntax, IFC schema, and normative specification rules.
                    </Typography>
                    {isLoggedIn ? (
                      <Link href="/dashboard" sx={{
                        color: '#fff', fontWeight: 700, textDecoration: 'none', fontSize: '1.1rem',
                        background: 'rgba(0,0,0,0.35)', border: 'solid 2px #fff',
                        padding: '0.6em 2em', borderRadius: '0.4em',
                        '&:hover': { background: 'rgba(0,0,0,0.55)' }
                      }}>Go to dashboard →</Link>
                    ) : (
                      <Link href="/login" sx={{
                        color: '#fff', fontWeight: 700, textDecoration: 'none', fontSize: '1.1rem',
                        background: 'rgba(0,0,0,0.35)', border: 'solid 2px #fff',
                        padding: '0.6em 2em', borderRadius: '0.4em',
                        '&:hover': { background: 'rgba(0,0,0,0.55)' }
                      }}>Sign in to start validating →</Link>
                    )}
                  </Container>
                </Box>

                <Box sx={{
                  alignSelf: "start",
                  background: "#fff",
                  padding: '0.5em 5em',
                  boxSizing: 'border-box',
                  borderTop: '2px solid gray',
                  width: '100%',
                  "& .MuiTypography-h5": { fontWeight: 700, margin: '0 0 2em 0', padding: 0, },
                  "& .MuiTypography-h6": { fontWeight: 100, margin: '3em 0 0 0', padding: 0, textTransform: 'uppercase' },
                }}>
                  <Container maxWidth="lg">
                    {isLoggedIn && (
                      <>
                        <Box sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          alignSelf: 'center',
                          borderRadius: '4px',
                          boxShadow: 'rgb(0 0 0 / 50%) 2px 2px 8px',
                          backgroundColor: '#ffffff',
                          padding: '0px 32px 0px 0px',
                          marginTop: '3em'
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
                        <Link href="/dashboard" sx={{ display: 'inline-block', mt: 1, fontWeight: 700, textDecoration: 'none', color: '#000', '&:hover': { borderBottom: 'dotted 1px black', color: '#333' } }}>View past validations →</Link>
                      </>
                    )}

                    <Typography variant='h6'>How it checks</Typography>
                    <Typography variant='h5'>Four layers of validation</Typography>

                    <Box
                      sx={{
                        display: "grid",
                        gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
                        gap: 2,
                        p: 0,
                      }}
                    >
                      {items.map(({ icon: Icon, title, desc }) => (
                        <Paper
                          key={title}
                          elevation={0}
                          sx={{
                            bgcolor: "#e7e7e7",
                            borderRadius: 3,
                            p: 3,
                            minHeight: 130,
                          }}
                        >
                          <Icon sx={{ fontSize: 22, mb: 1 }} />
                          <Typography sx={{ fontWeight: 700, mb: 1 }}>{title}</Typography>
                          <Typography variant="body2" sx={{ color: "text.secondary", lineHeight: 1.5 }}>
                            {desc}
                          </Typography>
                        </Paper>
                      ))}
                    </Box>

                    <Typography variant='h6'>How it works</Typography>
                    <Typography variant='h5'>Three simple steps</Typography>

                    <Stack spacing={3}>
                      {steps.map((s) => (
                        <Box
                          key={s.n}
                          sx={{
                            display: "grid",
                            gridTemplateColumns: "80px 1fr",
                            columnGap: 0,
                            alignItems: "start",
                          }}
                        >
                          <Typography
                            sx={{
                              fontSize: 44,
                              fontWeight: 800,
                              lineHeight: 1,
                              color: "rgba(0,0,0,0.22)",
                            }}
                          >
                            {s.n}
                          </Typography>

                          <Box>
                            <Typography sx={{ fontWeight: 800, lineHeight: 1.1 }}>
                              {s.title}
                            </Typography>
                            <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
                              {s.desc}
                            </Typography>
                          </Box>
                        </Box>
                      ))}
                    </Stack>

                    <Typography variant='h6'>FAQ</Typography>
                    <Typography variant='h5'>Common questions</Typography>


                    <Box sx={{ mx: "auto" }}>
                      {faqs.map((item, idx) => (
                        <Accordion
                          key={item.q}
                          disableGutters
                          elevation={0}
                          sx={{
                            borderTop: idx === 0 ? "1px solid rgba(0,0,0,0.2)" : "none",
                            borderBottom: "1px solid rgba(0,0,0,0.2)",
                            "&:before": { display: "none" },
                          }}
                        >
                          <AccordionSummary
                            sx={{
                              py: 3,
                              px: 0,
                              "& .MuiAccordionSummary-content": { my: 0 },
                            }}
                            expandIcon={
                              <Box sx={{ display: "grid", placeItems: "center" }}>
                                <AddIcon sx={{ fontSize: 22, ".Mui-expanded &": { display: "none" } }} />
                                <RemoveIcon
                                  sx={{ fontSize: 22, display: "none", ".Mui-expanded &": { display: "block" } }}
                                />
                              </Box>
                            }
                          >
                            <Typography sx={{ fontSize: 18, fontWeight: 700 }}>
                              {item.q}
                            </Typography>
                          </AccordionSummary>

                          <AccordionDetails sx={{ px: 0, pt: 0, pb: 3 }}>
                            <Typography sx={{ color: "text.secondary", maxWidth: 900 }}>
                              {item.a}
                            </Typography>
                          </AccordionDetails>
                        </Accordion>
                      ))}
                    </Box>

                    <Typography variant='h6'>Resources</Typography>
                    <Typography variant='h5'>Go deeper</Typography>

                    <Box
                      sx={{
                        display: "grid",
                        gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
                        gap: 2,
                        mb: '5em'
                      }}
                    >
                      {resources.map((r) => (
                        <Paper
                          key={r.title}
                          elevation={0}
                          sx={{
                            bgcolor: "#e7e7e7",
                            borderRadius: 3,
                            p: 3,
                            position: "relative",
                          }}
                        >
                          <Link
                            href={r.href}
                            underline="none"
                            color="inherit"
                            target={r.href.startsWith("http") ? "_blank" : undefined}
                            rel={r.href.startsWith("http") ? "noopener noreferrer" : undefined}
                            sx={{
                              display: "block",
                              height: "100%",
                              "&:hover .openIcon": { opacity: 1 },
                            }}
                          >
                            <OpenInNewIcon
                              className="openIcon"
                              sx={{
                                position: "absolute",
                                top: 14,
                                right: 14,
                                fontSize: 18,
                                opacity: 0.7,
                              }}
                            />
                            <Typography sx={{ fontSize: 12, fontWeight: 700, mb: 1 }}>
                              {r.kicker}
                            </Typography>
                            <Typography sx={{ fontSize: 18, fontWeight: 800, mb: 0.5 }}>
                              {r.title}
                            </Typography>
                            <Typography variant="body2" sx={{ color: "text.secondary" }}>
                              {r.desc}
                            </Typography>
                          </Link>
                        </Paper>
                      ))}
                    </Box>

                    <Footer />
                  </Container>
                </Box>

              </Grid>
            </div>
          </Grid>

          {isLoggedIn && <FeedbackWidget user={user} />}
          {isLoggedIn && <SelfDeclarationDialog user={user} />}

        </Grid>
      </Grid>
    </div>

  );
}

export default App;