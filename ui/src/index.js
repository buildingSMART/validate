import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import Dashboard from './Dashboard';

import Callback from './Callback';
import Logout from './Logout';
import Report from './Report';
import Page from './Page';

import reportWebVitals from './reportWebVitals';
import { BrowserRouter, Routes, Route } from "react-router-dom";

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  // <React.StrictMode>

  <BrowserRouter>
    <Routes>
      <Route path="/" element={<Page pageTitle="home"><App/></Page>} />
      <Route path="sandbox/:commitId/" element={<Page pageTitle="home"><App/></Page>} />

      <Route path="/dashboard" element={<Page pageTitle="dashboard"><Dashboard/></Page>} />
      <Route path="sandbox/dashboard/:commitId" element={<Page pageTitle="dashboard"><Dashboard/></Page>} />

      <Route path="/report/:modelCode"element={<Page pageTitle="report"><Report/></Page>} />
      <Route path="/sandbox/report/:commitId/:modelCode" element = {<Page pageTitle="report"><Report/></Page>} />

      <Route path="/callback" element={<Callback />} />
      <Route path="/logout" element={<Logout />} />
    </Routes>
  </BrowserRouter>
  // </React.StrictMode>
  );

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
