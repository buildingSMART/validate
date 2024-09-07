import { Sidetab } from '@typeform/embed-react';
import { VERSION, COMMIT_HASH } from './environment'

function FeedbackWidget({ user }) {    

    // Typeform widget
    return (
       
       <Sidetab
        id="cttcZ07p"
        medium="bsi-validation-service"
        hidden={{
            version: VERSION,
            commit_hash: COMMIT_HASH,
            user: user["email"]
        }}
        buttonText="Share feedback"
        />
    )
}

export default FeedbackWidget;
