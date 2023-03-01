import React, { useEffect, useContext } from "react";
import './Dz.css'
import { FETCH_PATH } from './environment'
import Button from '@mui/material/Button';
import { PageContext } from './Page';

function Dz() {

    const context = useContext(PageContext);
     
    useEffect(() => {
        window.Dropzone.autoDiscover = false;
        var dz = new window.Dropzone("#ifc_dropzone",
            {
                uploadMultiple: true,
                acceptedFiles: ".ifc, .xml",
                parallelUploads: 100,
                maxFiles: 100,
                maxFilesize: 8 * 1024,
                autoProcessQueue: false,
                addRemoveLinks: true,
            });

        dz.on("addedfile", file => { console.log("new file") });

        dz.on("success", function (file, response) {
            if (window.location.href.split("/").at(-1) != "dashboard"){
                window.location = response.url;
            }
            else{
                window.location.reload();
                dz.removeAllFiles();  
            }
        });

        var submitButton = document.querySelector("#submit");
        submitButton.addEventListener("click", function () {
            dz.processQueue();
        });


    }, []);

    return (
        <div>
            <div className="submit-area" id="ifc_tab">
                <form action={context.sandboxId?`${FETCH_PATH}/api/sandbox/${context.sandboxId}`:`${FETCH_PATH}/api/`} className="dropzone" id="ifc_dropzone">
                    <div className="dz-message" data-dz-message><span><i className="material-icons">file_upload</i> Click or drop files here to upload for validation</span></div>
                </form>
                <Button className="submit-button" variant="contained" id="submit">Upload & Validate</Button>
            </div>
        </div>
    );

}

export default Dz;