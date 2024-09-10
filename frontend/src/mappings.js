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
