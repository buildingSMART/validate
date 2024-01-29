import { useState, createContext } from 'react';
import ErrorBoundary from './ErrorBoundary'

function getSandboxId(pageTitle){
    const splittedUrl = window.location.href.split("/");
    if (pageTitle == "report"){
        return splittedUrl.includes("sandbox") ? splittedUrl.at(-2) : false
    }
    else{
        return splittedUrl.includes("sandbox") ? splittedUrl.at(-1):false
    }
}

function getEnvironment(pageTitle){
    const splittedUrl = window.location.href.split("/");
    return splittedUrl[2].split('.')[0];
 
}

export const PageContext = createContext(1);

export default function Page(props){

    const [sandboxId, setSetSandboxId] = useState(getSandboxId(props.pageTitle));
    const [pageTitle, setPageTitle] = useState(props.pageTitle);
    const [environment, setEnvironment] = useState(getEnvironment(props.pageTitle));

    return (

        <ErrorBoundary>
            <PageContext.Provider
                value={{sandboxId:sandboxId, pageTitle:pageTitle,environment:environment }}     
            >
                    {props.children}
            </PageContext.Provider>
        </ErrorBoundary>
    ) 
}