import React from "react";
import Grid from '@mui/material/Grid';
import Link from '@mui/material/Link';

import { FETCH_PATH } from './environment'
import { getCookieValue } from './Cookies';

const ErrorMessage = () => {
  return <Grid
      container
      spacing={0}
      direction="column"
      alignItems="center"
      style={{ minHeight: '100vh', paddingTop: '6vh', gap: '4vh', backgroundImage: 'url(' + require('./background.jpg') + ')', boxSizing: 'border-box'}}
    >
      <img style={{ width: '20vw', height: 'auto' }} src={require("./BuildingSMART_CMYK_validation_service.png")}/>
      <h1>Oops!</h1>
      <div>
        An error occured. Please try refreshing the page and contact <Link href="mailto:validate@buildingsmart.org" underline="none">{'validate@buildingsmart.org'}</Link>
      </div>
    </Grid>
  ;
};

export default class ErrorBoundary extends React.Component {
  state = {
    hasError: false,
    error: { message: "", stack: "" },
    info: { componentStack: "" }
  };

  static getDerivedStateFromError = error => {
    return { hasError: true };
  };

  componentDidCatch = (error, info) => {

    this.setState({ error, info });

    fetch(`${FETCH_PATH}/api/report_error`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json', 
        'x-csrf-token': getCookieValue('csrftoken') 
      },
      body: JSON.stringify({
        name: error.name,
        message: error.message,
        componentStack: info.componentStack
      }),
      credentials: 'include'
    });
  };

  render() {
    const { hasError, error, info } = this.state;
    console.log(error, info);
    const { children } = this.props;

    return hasError ? <ErrorMessage /> : children;
  }
}