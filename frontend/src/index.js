import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import Dashboard from './Dashboard';

import Callback from './Callback';
import Logout from './Logout';
import Report from './Report';
import Page from './Page';

import { FETCH_PATH, VERSION, COMMIT_HASH, PUBLIC_URL, NODE_ENV } from './environment';

import reportWebVitals from './reportWebVitals';
import { BrowserRouter, Routes, Route } from "react-router-dom";

console.log('REACT_APP_VERSION', VERSION)
console.log('REACT_APP_COMMIT_HASH', COMMIT_HASH)
console.log('REACT_APP_FETCH_PATH', FETCH_PATH)
console.log('PUBLIC_URL', PUBLIC_URL)
console.log('NODE_ENV', NODE_ENV)

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  // <React.StrictMode>

  <BrowserRouter>
    <Routes>
      <Route path="/" element={<Page pageTitle="home"><App/></Page>} />
      <Route path="sandbox/:commitId/" element={<Page pageTitle="home"><App/></Page>} />
      
      <Route path="/dashboard" element={<Page pageTitle="dashboard"><Dashboard/></Page>} />
      <Route path="sandbox/dashboard/:commitId" element={<Page pageTitle="dashboard"><Dashboard/></Page>} />

      <Route path="/report_syntax/:modelCode"element={<Page pageTitle="report"><Report kind="syntax"/></Page>} />
      <Route path="/report_schema/:modelCode"element={<Page pageTitle="report"><Report kind="schema"/></Page>} />
      <Route path="/report_bsdd/:modelCode"element={<Page pageTitle="report"><Report kind="bsdd"/></Page>} />
      <Route path="/report_rules/:modelCode"element={<Page pageTitle="report"><Report kind="normative"/></Page>} />
      <Route path="/report_file/:modelCode"element={<Page pageTitle="report"><Report kind="file"/></Page>} />
      <Route path="/report_industry/:modelCode"element={<Page pageTitle="report"><Report kind="industry"/></Page>} />

      <Route path="/sandbox/report_syntax/:commitId/:modelCode"element={<Page pageTitle="report"><Report kind="syntax"/></Page>} />
      <Route path="/sandbox/report_schema/:commitId/:modelCode"element={<Page pageTitle="report"><Report kind="schema"/></Page>} />
      <Route path="/sandbox/report_bsdd/:commitId/:modelCode"element={<Page pageTitle="report"><Report kind="bsdd"/></Page>} />
      <Route path="/sandbox/report_rules/:commitId/:modelCode"element={<Page pageTitle="report"><Report kind="normative"/></Page>} />
      <Route path="/sandbox/report_file/:commitId/:modelCode"element={<Page pageTitle="report"><Report kind="file"/></Page>} />
      <Route path="/sandbox/report_industry/:commitId/:modelCode"element={<Page pageTitle="report"><Report kind="industry"/></Page>} />
      
      <Route path="/callback" element={<Callback />} />
      <Route path="/logout" element={<Logout />} />
      <Route path="/waiting_zone" element={<Page pageTitle="waiting_zone"><App/></Page>} />      
    </Routes>
  </BrowserRouter>
  
  // </React.StrictMode>
  );

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
