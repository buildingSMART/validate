

function sendInfo(index = null) {
    console.log(this)
    var property = event.srcElement.id.split('_')[0];
    var modelCode = event.srcElement.id.split('_')[1];
    console.log(modelCode)
    var data = { type: property, val: this.value, code: modelCode};

    fetch("/update_info/" + modelCode, {
        method: "POST",
        body: JSON.stringify(data)
    }).then(function (r) { return r.json(); }).then(function (r) {
        console.log(r);
    })
}

// Helper functions
function createLicenseInput(licensTypes, row, model){
    var licenseSelect = document.createElement("SELECT");

    for (const license of licensTypes) {
        var option = document.createElement("option");
        option.text = license;
        licenseSelect.add(option);
    }

    licenseSelect.id = "license_" + model.code;
    licenseSelect.addEventListener("change", sendInfo);
    licenseSelect.value = model.license
    row.cells[toColumnComplete["license"]].appendChild(licenseSelect);

}

function createInput(type, row, model){
    if (toColumnComplete[type]) {
    var input = document.createElement("INPUT")
    input.id = `${type}_${model.code}`;
    input.addEventListener("change", sendInfo);
    input.value = (type=="hours" ? model.hours : model.details);
    row.cells[toColumnComplete[type]].appendChild(input);
    }
}

function replaceInCell(type, cell, modelId, replace=0){
    if(replace){
        cell.removeChild(cell.childNodes[0]);
    }
    cell.className = type;
    var a = document.createElement('a');
    var text = (type=="download") ? "Download":"Delete";
    var linkText = document.createTextNode(text);
    a.className = "dashboard_link"
    a.appendChild(linkText);
    a.title = type;
    a.href = `/${type}/${modelId}`;
    cell.appendChild(a);
}


var icons = { 'v': 'valid', 'w': 'warning', 'i': 'invalid', 'n': 'not' };
function completeTable(i) {
    var table = document.getElementById("saved_models");
    var row_index = idToRowIndex[modelIds[i]];
    var rows = table.rows;

    fetch("/reslogs/" + i + "/" + unsavedConcat).then(function (r) { return r.json(); }).then(function (r) {
        ['syntax', 'schema', 'mvd', 'bsdd', 'ia', 'ip'].forEach((x, i) => {
            var icon = icons[r["results"][`${x}log`]];
            
            rows[row_index].cells[toColumnComplete[x]].className = `${icon} material-icons`;
          });

        rows[row_index].cells[toColumnComplete["date"]].innerHTML = r["time"];
        rows[row_index].cells[toColumnComplete["date"]].className = "model_time";

    });


    rows[row_index].cells[toColumnComplete["report"]].className = "model_report";
    var repText = document.createElement("a");
    repText.className = "dashboard_link";
    repText.id = "report";
    repText.innerHTML = "View report";
    repText.target = "_blank";
    repText.href = `/report2/${savedModels[i].code}`;
    rows[row_index].cells[toColumnComplete["report"]].appendChild(repText);

    replaceInCell("download",rows[row_index].cells[toColumnComplete["download"]], savedModels[i].id, 1);
    replaceInCell("delete",rows[row_index].cells[toColumnComplete["delete"]], savedModels[i].id, 1);
}

var table = document.getElementById("saved_models");
var nCols = Object.keys(toColumnComplete).length;
var unsavedConcat = "";
var modelIds = [];
var codeToId = {};
var idToRowIndex = {}


if(savedModels.length == 0){
    var rowIndex = 1;
    var row = table.insertRow(rowIndex);
    row.insertCell(0);
    row.cells[0].innerHTML = "No model uploaded";
}

else{

    savedModels.forEach((model, i) => {
        var rowIndex = i + 1;
        var row = table.insertRow(rowIndex);
        row.id = model.id;
    
        for (var col = 0; col < nCols; col++) {
            row.insertCell(col);
        }
    
        row.cells[toColumnComplete["file_format"]].className = "ifc";
    
        row.cells[toColumnComplete["file_name"]].innerHTML = model.filename;
        row.cells[toColumnComplete["file_name"]].className = "filename";
    
        
        var licensTypes = ["private", "CC", "MIT", "GPL", "LGPL"];
    
        createLicenseInput(licensTypes, row, model);
        createInput("hours", row, model);
        createInput("details", row, model);
    
        if (model.progress == 100 || model.progress == -2) {
            var checks_type = ["syntax", "schema", "mvd", "bsdd", "ids", "ia", "ip"];
            var icons = { 'v': 'valid', 'w': 'warning', 'i': 'invalid', 'n': 'not' };
            for (var j = 0; j < checks_type.length; j++) {
                var attr = "status_" + checks_type[j];
                var status_result = model[attr];
                var icon = icons[status_result];
                if (toColumnComplete[checks_type[j]]) {
                    row.cells[toColumnComplete[checks_type[j]]].className = `material-icons ${icon}`;
                }
            }
    
            var repText = document.createElement("a");
            repText.id = "report";
            repText.innerHTML = "View report";
            repText.target = "_blank";
            repText.href = `/report2/${model.code}`;
    
            row.cells[toColumnComplete["report"]].appendChild(repText)
            row.cells[toColumnComplete["report"]].className = "model_report"
    
            row.cells[toColumnComplete["date"]].innerHTML = model.date
            row.cells[toColumnComplete["date"]].className = "model_time"
    
            replaceInCell("download",row.cells[toColumnComplete["download"]], model.id);
            replaceInCell("delete",row.cells[toColumnComplete["delete"]], model.id);
    
            row.cells[toColumnComplete["geoms"]].innerHTML = model.number_of_geometries;
            row.cells[toColumnComplete["props"]].innerHTML = model.number_of_properties;
    
        }
    
        else {
            console.log("unsaved");
            unsavedConcat += model.code;
            modelIds.push(model.id);
    
            idToRowIndex[model.id] = rowIndex;
    
            row.cells[toColumnUncomplete["stop"]].innerHTML = "&#8634";
    
            const newDiv = document.createElement("div");
            newDiv.className = "progress"
            const barDiv = document.createElement("div");
            barDiv.id = "bar" + model.id;
            barDiv.className = "bar";
            newDiv.appendChild(barDiv)
            row.cells[toColumnUncomplete["progress"]].appendChild(newDiv);
    
            row.cells[toColumnUncomplete["advancement"]].innerHTML = model.progress;
            row.cells[toColumnUncomplete["advancement"]].id = "percentage" + model.id;
            codeToId[model.code] = model.id;
    
    
        }
    });

}

const registered = new Set();
function poll(unsavedConcat) {
    fetch("/valprog/" + unsavedConcat).then(function (r) { return r.json(); }).then(function (r) {
        for (var i = 0; i < r.progress.length; i++) {
            var str = unsavedConcat;
            var modelCode = str.match(/.{1,32}/g)
            var id = codeToId[modelCode[i]]
            var percentage = document.getElementById("percentage" + id)
            var bar = document.getElementById("bar" + id)

            var file_row = document.getElementById(id)
            file_row.cells[toColumnUncomplete["geoms"]].innerHTML = r["file_info"][i]["number_of_geometries"]
            file_row.cells[toColumnUncomplete["props"]].innerHTML = r["file_info"][i]["number_of_properties"]

            if (r.progress[i] === 100) {

                if (!registered.has(i)) {

                    registered.add(i);

                    bar.style.width = 100 * 2 + 'px';
                    percentage.innerHTML = "100%"
                    completeTable(i);

                }

            } else {
                var p = r.progress[i];
                if (p < 0) {
                    percentage.innerHTML = "<i>in queue</i>";
                    p = 0
                } else {
                    percentage.innerHTML = p + "%";
                }
                bar.style.width = p * 2 + 'px';

            }

        }

        setTimeout( () => { poll(unsavedConcat) }, 1000);
        // setTimeout(poll(unsavedConcat), 1000);

    });

}


if (unsavedConcat) {
    console.log("/valprog/" + unsavedConcat);
    
    poll(unsavedConcat);

}

