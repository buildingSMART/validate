import './App.css';
import { useState, useEffect } from 'react';

function Logout() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
      fetch('/api/logout')
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
