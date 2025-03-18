import * as React from 'react';

import { Typography } from '@mui/material';
import Button from '@mui/material/Button';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';

import HelpOutlinedIcon from '@mui/icons-material/HelpOutlined';
import Tooltip from '@mui/material/Tooltip';

import { useEffect, useState } from 'react';
import { FETCH_PATH } from './environment';
import { getCookieValue } from './Cookies';

function SelfDeclarationDialog({ user }) {    

    const [open, setOpen] = useState(false);
    const [selectedOption, setSelectedOption] = useState(null);

    useEffect(() => {
        // TEMPORARY - IVS-433: don't show this dialog just yet
        //setOpen(user['is_vendor_self_declared'] === null);
    }, []);

    const handleRadioChange = (event) => {
        setSelectedOption(event.target.value);
    };

    const handleSubmit = () => {

        fetch(`${FETCH_PATH}/api/me`, {
                method: 'POST',
                body: JSON.stringify({ is_vendor_self_declared: selectedOption }),
                headers: { 
                    'x-csrf-token': getCookieValue('csrftoken'),
                    'Content-Type': 'application/json',
                },
                credentials: 'include'
            })
            .then((response) => response.json())
            .then((json) => {
                // setSelected([])
            });
        handleClose();
    };
    
    const handleClose = () => {
        setOpen(false);
    };

    return (
       
        <Dialog
            open={open}
            onClose={() => {}} // prevent ESC or close by clicking away
            fullWidth='true'
            maxWidth='md'
        >
            <DialogTitle>Self-Declaration of Affiliation</DialogTitle>
            <DialogContent>
                <DialogContentText>
                    Please confirm whether you are affiliated with a software company implementing IFC.
                </DialogContentText>
                <br />
                <FormControl>
                    <RadioGroup onChange={handleRadioChange}>
                        <FormControlLabel value="True" control={<Radio />} label="I am affiliated with a software company implementing IFC in their tools" />
                        <FormControlLabel value="False" control={<Radio />} label="I am a regular user, and NOT affiliated with any software company implementing IFC" />
                    </RadioGroup>
                </FormControl>            
            </DialogContent>
            <DialogActions>
                <div>
                <Typography variant="caption" align='left'>
                    <Tooltip title='We are asking this because we only include non-vendor affiliated validation results in our Scorecards.'>
                        <HelpOutlinedIcon fontSize="xsmall" color="primary" /> Why are we asking this?
                    </Tooltip>
                </Typography>
                </div>
                
                <Button disabled={selectedOption === null} onClick={handleSubmit}>Continue</Button>
                
            </DialogActions>
        </Dialog>
    )
}

export default SelfDeclarationDialog;
