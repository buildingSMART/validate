import ifcopenshell
import sys 
import requests
import json
import argparse
from helper import database



def get_classification_object(uri):
    url = "https://bs-dd-api-prototype.azurewebsites.net/api/Classification/v3"
    return requests.get(url, {'namespaceUri':uri})

def validate_ifc_classification_reference(relating_classification):
    uri = relating_classification.Location
    bsdd_response = get_classification_object(uri)
    if bsdd_response.status_code != 200:
        return 0
    elif bsdd_response.status_code == 200:
        return bsdd_response

def has_specifications(bsdd_response_content):
    if bsdd_response_content["classificationProperties"]:
        return 1
    else:
        return 0

def validate_instance(constraint,ifc_file, instance):

    result = {"pset_name":"pset not found","property_name":"pset not found","value":"pset not found","datatype":"pset not found" }
    constraint = {
        "specified_pset_name":constraint["propertySet"],
        "specified_property_name" : constraint["name"],
        "specified_datatype" : constraint["dataType"],
        "specified_predefined_value" : constraint["predefinedValue"],
    }


    # Integrate these:
    #   "maxExclusive": 0
    #   "maxInclusive": 0
    #   "minExclusive": 0
    #   "minInclusive": 0
    #   "pattern": ""

    for definition in instance.IsDefinedBy:
        if definition.is_a() == "IfcRelDefinesByProperties":
            
            pset = definition.RelatingPropertyDefinition
            if pset.Name == constraint["specified_pset_name"]:
                result["property_name"] = "property not found"
                result["value"] = "property not found"
                result["datatype"] = "property not found"

                result = {"pset_name":pset.Name,"property_name":"pset not found","value":"pset not found","datatype":"pset not found" }
                for property in pset.HasProperties:
                    if property.Name == constraint["specified_property_name"]:
                        result["property_name"] = property.Name

                        if isinstance(property.NominalValue, ifcopenshell.entity_instance):
                            result["value"] = property.NominalValue[0]
                            result["datatype"] = type(property.NominalValue[0])
                        else:
                            result["value"] = property.NominalValue
                            result["datatype"] = type(property.NominalValue[0])

                        

    return {"constraint":constraint,"result":result}



def check_bsdd(ifc_fn, task_id):
   
    file_code = ifc_fn.split(".ifc")[0]
    ifc_file = ifcopenshell.open(ifc_fn)
   
    with database.Session() as session:
        model = session.query(database.model).filter(database.model.code == file_code)[0]
        file_id = model.id
        
        n = len(ifc_file.by_type("IfcRelAssociatesClassification"))
        if n:
            percentages = [i * 100. / n for i in range(n+1)]
            num_dots = [int(b) - int(a) for a, b in zip(percentages, percentages[1:])]

        for idx, rel in enumerate(ifc_file.by_type("IfcRelAssociatesClassification")):

            sys.stdout.write(num_dots[idx] * ".")
            sys.stdout.flush()

            related_objects = rel.RelatedObjects
            relating_classification = rel.RelatingClassification

            bsdd_response = validate_ifc_classification_reference(relating_classification)
            bsdd_content = json.loads(bsdd_response.text)
            
            for ifc_instance in related_objects:
                instance = database.ifc_instance(ifc_instance.GlobalId, ifc_instance.is_a(), file_id)
                session.add(instance)
                session.flush()
                instance_id = instance.id
                session.commit()               

                if bsdd_response:
                    if has_specifications(bsdd_content):
                        specifications = bsdd_content["classificationProperties"]
                        for constraint in specifications: 
                            bsdd_result = database.bsdd_result(task_id)
                            # Should create instance entry
                            bsdd_result.instance_id = instance_id

                            bsdd_result.bsdd_classification_uri = bsdd_content["namespaceUri"]
                            bsdd_result.bsdd_type_constraint = ";".join(bsdd_content["relatedIfcEntityNames"])
                            bsdd_result.bsdd_property_constraint = json.dumps(constraint)
                            bsdd_result.bsdd_property_uri = constraint["propertyNamespaceUri"]

                            results = validate_instance(constraint, ifc_file, ifc_instance)["result"]

                            bsdd_result.ifc_property_set = results["pset_name"]
                            bsdd_result.ifc_property_name = results["property_name"]
                            
                            if not isinstance(results["datatype"], str):
                                bsdd_result.ifc_property_type = results["datatype"].__name__
                            bsdd_result.ifc_property_value = results["value"]

                            session.add(bsdd_result)
                            session.commit()
                    else:
                        # Record NULL in other fields
                        bsdd_result = database.bsdd_result(task_id)
                        bsdd_result.bsdd_property_constraint = "no constraint"
                        session.add(bsdd_result)
                        session.commit()
                else:
                    # Record NULL everywhere in bsdd_result
                    bsdd_result = database.bsdd_result(task_id)
                    bsdd_result.bsdd_classification_uri = "classification not found"
                    session.add(bsdd_result)
                    session.commit()
                
        #todo: implement scores that actually validate or not the model
        model = session.query(database.model).filter(database.model.code == file_code)[0]
        model.status_bsdd = 'v'
        session.commit()

if __name__=="__main__":
        parser = argparse.ArgumentParser(description="Generate classified IFC file")
        parser.add_argument("--input","-i", default="Duplex_A_20110505.ifc", type=str)
        parser.add_argument("--task","-t", default=0, type=int)

        args = parser.parse_args()
        check_bsdd(args.input, args.task)





