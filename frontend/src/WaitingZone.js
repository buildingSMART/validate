import {useContext, useEffect, useState} from "react";
import Grid from '@mui/material/Grid';
import Divider from '@mui/material/Divider';
import Link from '@mui/material/Link';
import HomeIcon from '@mui/icons-material/Home';
import MailIcon from '@mui/icons-material/Mail';

import Footer from './Footer';

import {FETCH_PATH} from "./environment";
import {getCookieValue} from "./Cookies";
import {PageContext} from "./Page";

const Mailto = ({ email, subject = "", body = "", children }) => {
  const params =
    subject || body
      ? `?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(
          body
        )}`
      : "";

  return <a href={`mailto:${email}${params}`}>{children}</a>;
};


export default function WaitingZone() {

  const [isLoggedIn, setLogin] = useState(false);
  const [user, setUser] = useState(null);

  const [prTitle, setPrTitle] = useState("")

  const context = useContext(PageContext);

  useEffect(() => {
    fetch(context.sandboxId ? `${FETCH_PATH}/api/sandbox/me/${context.sandboxId}` : `${FETCH_PATH}/api/me`, { credentials: 'include', 'x-csrf-token': getCookieValue('csrftoken') })
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
          <Grid>
              <Link>
                  <img src={require("./logo.png")} style={{height: "130px"}} alt="Validation Service - Logo"/>
              </Link>
              <Divider/>
              <div style={{width: '65%', margin: '0 auto'}}>
                  <br/>
                  <h2>
                      Awaiting User Activation
                  </h2>
                  <br/>
                  <MailIcon/>
                  <Mailto
                      email="validate@buildingsmart.org"
                      subject="Access Request (Generated from website)"
                      body={"Please activate my account." + `\n\nUsername=${user['name']}\nEmail=${user['email']}`}
                      >
                      Request Access
                  </Mailto>
                  <br/>
                  <HomeIcon/>
                  <a href="/">Home</a>
                  <br/>
              </div>
              <div>
                  <br/>
                  <Divider/>
                  <Footer/>
              </div>
          </Grid>
      );
  }
}