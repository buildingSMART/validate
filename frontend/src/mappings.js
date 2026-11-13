export const statusToColor = 
{
    "v": "rgb(217, 242, 217)",
    "i": "rgb(255, 204, 204)",
    "n": "#dddddd",
    "w": "rgb(253, 253, 150)",
    "p": "#dddddd",
};

export const statusToLabel = 
{
    "v": "Valid",
    "i": "Invalid",
    "n": "N/A",
    "w": "Warning",
    "p": "Pending..."
};

export const severityToStatus = 
{
    0: "n",  // n/a or disabled
    1: "v",  // executed
    2: "v",  // passed
    3: "w",  // warning
    4: "i",  // error
};

export const severityToLabel = 
{
    0: "N/A",
    1: "Applicable",
    2: "Passed",
    3: "Warning",
    4: "Error",
};

export const severityToColor = 
{
    0: "#dddddd", // N/A
    1: "rgb(217, 242, 217)", // executed
    2: "rgb(217, 242, 217)", // passed
    3: "rgb(253, 253, 150)", // warning
    4: "rgb(255, 204, 204)", // error
};

// IFC file header policy (backend checks/header_policy/validate_header.py): field keys as they
// appear in header_validation.validation_errors / validation_details, in File Info table order
export const headerFieldLabels =
{
    "description": "MVD(s)",
    "name": "File Name in Header",
    "time_stamp": "File Date",
    "originating_system": "Originating System",
    "preprocessor_version": "Preprocessor Version",
    "company_name": "Company Name",
    "application_name": "Application Name",
    "version": "Application Version",
    "author": "Author",
    "organization": "Organization",
    "authorization": "Authorization",
    "implementation_level": "Implementation Level",
    "comments": "Comment",
    "syntax_error": "Header Syntax",
};

export const headerFieldDescriptions =
{
    "description": "One or more model view definitions used in the context of this data exchange.",
    "name": "The string of graphic characters used to name this particular instance of an exchange structure",
    "file_name": "The string of graphic characters used to name this particular instance of an exchange structure",
    "time_stamp": "The date and time specifying when the exchange structure was created, formatted in ISO 8601",
    "originating_system": "The software from which the model originated, also known as the authoring tool.",
    "preprocessor_version": "The system used to create the exchange structure, including the system product name and version.",
    "version": "The version of the model or file format used, derived from the originating system",
    "company_name": "The name of the company, derived from the originating system",
    "application_name": "The software used to export the model, derived from the originating system",
    "authorization": "The name and mailing address of the person who authorized the sending of the exchange structure.",
    "organization": "The group or organization with whom the author is associated.",
    "author": "The name and mailing address of the person responsible for creating the exchange structure.",
    "implementation_level": "The conformance class and implementation level of the exchange structure.",
    "comments": "Free text comment in the description, limited to 256 characters.",
    "syntax_error": "The file header could not be parsed; see the STEP Syntax Report.",
};

export const HEADER_POLICY_URL = "https://github.com/buildingSMART/IFC4.x-IF/tree/main/docs/IFC-file-header";

export function headerPolicyUrl(field) {
    return `${HEADER_POLICY_URL}#${field}`;
}
