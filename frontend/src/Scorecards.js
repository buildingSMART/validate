import ConstructionIcon from '@mui/icons-material/Construction';

export default function Scorecards() {

    return (
        <div style={{ width: '65%', margin: '0 auto' }}>
            <h1>Scorecards Service</h1>

            <h2>What is the Scorecards Service?</h2>
            <p>
                The Scorecards Service is an online platform developed and operated by buildingSMART. It provides an overview of the extent to which various software applications support the IFC standard.
            </p>

            <p style={{ textAlign: 'center', paddingTop: '20px', paddingBottom: '20px' }}>
                <img src={require('./scorecards.png')} title="Screenshot of the buildingSMART Scorecards Service" />
                <br /><small>Screenshot of the buildingSMART Scorecards Service</small>
            </p>

            <h2>How does it work?</h2>
            <p>
                The Scorecards Service analyzes the validation outcomes of IFC files that users check through the IFC Validation Service. 
                Based on these results, it generates and aggregates metrics to evaluate each tool used to create the IFC files. 
                The criteria and methodology used to generate the scorecards are outlined in the Process & Principles section below.
            </p>

            <h2>Who is this service intended for?</h2>
            <p>
                The Scorecards Service is designed for anyone who wants to understand which parts of the IFC standard are supported by a specific version of a particular tool.
            </p>

            <b>! IMPORTANT !</b>
            <p>
                The scorecards approach is <b>not</b> intended to criticize tools or vendors. Instead, this free, transparent service aims to help improve the quality of IFC files and, ultimately, to support vendors in enhancing their implementations of the standard for the parts they choose to support.
            </p>

            <h2>Still under construction <ConstructionIcon /></h2> 
            <p>
                The Scorecards Service is currently under development. A prototype was presented to software vendors at the end of 2024, for their feedback. 
            </p>
            <p>
                buildingSMART is working to finalize the service and make it open and available to all in 2025.
            </p>
        </div>
    );

}