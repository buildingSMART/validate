import { useState, useEffect } from 'react';


const queryString = window.location.search;
const urlParams = new URLSearchParams(queryString);
const code = urlParams.get('code');


function Callback() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
      fetch(`/api/callback/${code}`)
        .then(response => response.json())
        .then((data) => {
          window.location.href = data.redirect;
        })
    },[]);

  if(visible){
    return null;
  }
}

export default Callback;
