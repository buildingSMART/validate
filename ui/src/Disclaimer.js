import Link from '@mui/material/Link';

function Disclaimer(){
    return (
        <div style={{backgroundColor: '#ffffff80', padding: '0.5em 1em'}}>Let us know what we're getting right and what we can improve at <Link href="mailto:validate@buildingsmart.org" underline="none">{'validate@buildingsmart.org'}</Link>
        </div>
    )
}

export default Disclaimer;