import './App.css';
import { useState, useEffect } from 'react';
import { FETCH_PATH } from './environment'

function Logout() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
      fetch(`${FETCH_PATH}/api/logout`)
        .then(response => response.json())
        .then((data) => {
          window.location.href = data.redirect;
        })
    },[]);
  
  if(visible){
    return null;
  }
}

export default Logout;
