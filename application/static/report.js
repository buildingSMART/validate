// var bsdd_validation_task = {{ bsdd_validation_task| tojson}};
// var bsdd_results = {{ bsdd_results| tojson}};
// var instances = {{ instances| tojson}};

console.log(bsdd_validation_task)
console.log(instances)
console.log(bsdd_results)

for(var i=-0;i<bsdd_results.length;i++){
    var constraint = bsdd_results[i]["bsdd_property_constraint"]
    // constraint =  JSON.parse(constraint)
    // bsdd_results[i]["bsdd_property_constraint"] = constraint
}


console.log(bsdd_results)