import * as React from 'react';

import { Typography, Box } from '@mui/material';
import { styled } from '@mui/material/styles';
import Button from '@mui/material/Button';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';

import HelpOutlinedIcon from '@mui/icons-material/HelpOutlined';
import Tooltip, { tooltipClasses } from '@mui/material/Tooltip';

import { useEffect, useState } from 'react';
import { FETCH_PATH } from './environment';
import { getCookieValue } from './Cookies';


const HtmlTooltip = styled(({ className, ...props }) => (
    <Tooltip {...props} classes={{ popper: className }} />
  ))(({ theme }) => ({
    [`& .${tooltipClasses.tooltip}`]: {
      backgroundColor: '#f5f5f9',
      color: 'rgba(0, 0, 0, 0.87)',
      maxWidth: 300,
      fontSize: theme.typography.pxToRem(12),
      border: '1px solid #dadde9',
    },
  }));

export default function SelfDeclarationDialog({ user }) {    

    const [open, setOpen] = useState(false);
    const [selectedOption, setSelectedOption] = useState(null);

    useEffect(() => {
        setOpen(user['is_vendor_self_declared'] === null);
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
            fullWidth={true}
            maxWidth='md'
        >
            <DialogTitle>Self-Declaration of Affiliation</DialogTitle>
            <DialogContent>
                <DialogContentText>
                    Please confirm whether you are affiliated with a software company implementing IFC.
                </DialogContentText>
                <br />
                <FormControl component="fieldset">
                    <RadioGroup onChange={handleRadioChange}>
                        <FormControlLabel value="True" control={<Radio />} label="I am affiliated with a software company implementing IFC in their tools" />
                        <FormControlLabel value="False" control={<Radio />} label="I am a regular user, and NOT affiliated with any software company implementing IFC" />
                    </RadioGroup>
                </FormControl>
                <br />
                <br />
                <Typography variant="caption">
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                        <HtmlTooltip
                            title={
                            <React.Fragment>                            
                                When IFC files are checked, the validation outcomes are used to generate an overview of the IFC support of the producing software.<br />
                                <br />
                                Read more about the <a href="/scorecards" target='_blank'>Scorecards Service</a>.
                            </React.Fragment>
                            }>
                            <HelpOutlinedIcon fontSize="xsmall" color="primary" /> Why are we asking this?
                        </HtmlTooltip>
                        <Button disabled={selectedOption === null} onClick={handleSubmit}>Continue</Button>
                    </Box>
                    
                </Typography>

            </DialogContent>
        </Dialog>
    )
}