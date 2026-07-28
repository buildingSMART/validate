import Grid from '@mui/material/Grid';
import Divider from '@mui/material/Divider';
import Link from '@mui/material/Link';
import HomeIcon from '@mui/icons-material/Home';

import Footer from './Footer';

export default function WaitingZone() {

    return (
        <Grid>
            <Link>
                <img src={require("./logo.png")} style={{height: "130px"}} alt="Validation Service - Logo"/>
            </Link>
            <Divider/>
            <div style={{width: '65%', margin: '0 auto'}}>
                <br/>
                <h2>
                    Awaiting User Activation
                </h2>
                <br/>
                <h4>
                    Thank you! We will review your request to activate your account soon.<br/>
                </h4>
                <br/>
                <HomeIcon/>
                <a href="/">Home</a>
                <br/>
            </div>
            <div>
                <br/>
                <Divider/>
                <Footer/>
            </div>
        </Grid>
    );
}