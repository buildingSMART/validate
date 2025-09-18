import React, { useEffect, useContext } from "react";
import './Dz.css'
import { FETCH_PATH } from './environment'
import Button from '@mui/material/Button';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import { PageContext } from './Page';
import { getCookieValue } from './Cookies';
import { AlertTitle } from "@mui/material";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";

function FileSizeWarning() {
    return (
        <Alert
        severity="warning"
        icon={<WarningAmberIcon fontSize="inherit" />}
        sx={{ borderRadius: 2, mb: 2 }}
        >
        <AlertTitle>Notice</AlertTitle>
        Files of over <strong>128 MB</strong> trigger an experimental processing pipeline.  
        Please report any issues to <a href="mailto:validate@buildingsmart.org">validate@buildingsmart.org</a>.
        </Alert>
    );
}

function Dz() {

    const MAX_FILE_SIZE_IN_MB = 512;
    const EXPERIMENTAL_FILE_SIZE_IN_MB = 256;
    const TOAST_DURATION = 5000; // ms

    const context = useContext(PageContext);
    
    const [showExperimentalWarning, setShowExperimentalWarning] = React.useState(false);

    const [showErrorToast, setShowErrorToast] = React.useState({
        open: false,
        fileName: '',
        fileSize: 0
    });
    const { open, fileName, fileSize } = showErrorToast;

    const handleSnackbarClose = (event, reason) => {

        if (reason === 'clickaway') {
            return;
        }

        setShowErrorToast({ ...showErrorToast, open: false });
    };

    useEffect(() => {
        window.Dropzone.autoDiscover = false;
        var dz = new window.Dropzone("#ifc_dropzone", {
            uploadMultiple: true,
            acceptedFiles: ".ifc",
            parallelUploads: 100,
            maxFiles: 100,
            maxFileSize: MAX_FILE_SIZE_IN_MB,
            autoProcessQueue: false,
            addRemoveLinks: true,
            withCredentials: true,
            headers: { 'x-csrf-token': getCookieValue('csrftoken') }
        });

        function showWarningWhenFileExceedsExperimentalTreshold() {
            setShowExperimentalWarning(
                dz.files.some(f => f.size > EXPERIMENTAL_FILE_SIZE_IN_MB * 1024 * 1024)
            );
        }

        dz.on("success", function (file, response) {
            if (window.location.href.split("/").at(-1) !== "dashboard"){
                window.location = response.url;
            }
            else{
                window.location.reload();
                dz.removeAllFiles();  
            }
        });

        dz.on("error", function (file, message) {

            //console.log(file.name, file.size, message);

            // block files that are too big
            if (message.indexOf('too big') !== -1) {
                dz.removeFile(file);
                setShowErrorToast({ 
                    ...showErrorToast, 
                    open: true, 
                    fileName: file.name, 
                    fileSize: Math.ceil(file.size / (1024 * 1024))
                });
            }
        });

        dz.on("totaluploadprogress", function (progress) {
            const pb = document.querySelector(".dropzone .progress-bar");
            const w = (pb.parentNode.offsetWidth - 2) / 100. * progress;
            pb.style.width = `${w}px`;
        });

        dz.on("addedfiles", showWarningWhenFileExceedsExperimentalTreshold);
        dz.on("removedfile", showWarningWhenFileExceedsExperimentalTreshold);
        
        var submitButton = document.querySelector("#submit");
        submitButton.addEventListener("click", function () {
            const pb = document.querySelector(".dropzone .progress-bar");
            pb.style.display = 'block';
            pb.style.width = `0px`;
            dz.processQueue();
        });

    }, []);

    return (
        <div>
            <div className="submit-area" id="ifc_tab">
                {showExperimentalWarning && <FileSizeWarning />}
                <form action={context.sandboxId?`${FETCH_PATH}/api/sandbox/${context.sandboxId}`:`${FETCH_PATH}/api/`} className="dropzone" id="ifc_dropzone">
                    <div className="progress-bar"></div>
                    <div className="dz-message" data-dz-message><span><i className="material-icons">file_upload</i> Click or drop files here to upload for validation</span></div>
                </form>
                <Button className="submit-button" variant="contained" id="submit">Upload & Validate</Button>
                <Snackbar
                    open={open}
                    autoHideDuration={TOAST_DURATION}
                    onClose={handleSnackbarClose}
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                >
                    <Alert
                        onClose={handleSnackbarClose}
                        severity='error'
                        variant='filled'
                        sx={{ width: '100%' }}
                    >
                        Oops! File Size Limit Reached <br />
                        <br />
                        You've attempted to upload a file larger than {MAX_FILE_SIZE_IN_MB} MB.<br />
                        Need assistance with larger files? Don't worry, we've got you covered! Contact our support team for tailored solutions.<br />
                    </Alert>
                </Snackbar>
            </div>
            
        </div>
    );

}

export default Dz;
