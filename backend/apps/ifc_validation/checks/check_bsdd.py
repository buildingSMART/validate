import ifcopenshell
import logging
import sys
import requests
import json
import argparse
import functools


logger = logging.getLogger()


@functools.lru_cache(maxsize=128)
def find_dictionary_by_uri(uri):

    url = "https://api.bsdd.buildingsmart.org/api/Dictionary/v1"
    response = requests.get(url, {'uri': uri })
    if response.status_code == 200:
        json = response.json()
        return json['dictionaries'][0] if json['count'] == 1 else None
    return None    


@functools.lru_cache(maxsize=128)
def get_dictionary(uri):

    url = "https://api.bsdd.buildingsmart.org/api/Dictionary/v1"
    uri_ = uri.split("/class")[0]
    try:
        response = requests.get(url, {'Uri':uri_})
        return response.json()['dictionaries'][0] if response.status_code == 200 else None
    except:
        class_ = get_class(uri)
        if class_:
            uri_ = class_['dictionaryUri']
            response = requests.get(url, {'Uri':uri_})
            return response.json()['dictionaries'][0] if response.status_code == 200 else None
        else:
            return None


@functools.lru_cache(maxsize=128)
def get_dictionaries():
    
    url = "https://api.bsdd.buildingsmart.org/api/Dictionary/v1"
    
    dictionaries = []
    count = 0
    total_count = 1000
    
    while count < total_count:
        response = requests.get(url + f'?offset={count}&limit=250')
        json = response.json()
        dictionaries += json['dictionaries']
        total_count = json['totalCount']
        count = json['count']
    
    return dictionaries


@functools.lru_cache(maxsize=128)
def find_dictionary_by_name(name, edition = None):

    all_dictionaries = get_dictionaries()
    dict_filter = lambda x: x['name'] == name and (edition is None or x['version'] == edition)
    filtered_dictionaries = list(filter(dict_filter, all_dictionaries))
    return filtered_dictionaries if len(filtered_dictionaries) else None


@functools.lru_cache(maxsize=128)
def get_class(uri):

    url = "https://api.bsdd.buildingsmart.org/api/Class/v1"
    response = requests.get(url, {'Uri':uri})
    return response.json() if response.status_code == 200 else None


@functools.lru_cache(maxsize=128)
def get_classes(uri):

    url = "https://api.bsdd.buildingsmart.org/api/Dictionary/v1/Classes"
    uri = uri.split("/class")[0]
    response = requests.get(url, {'Uri':uri})
    return response.json()['classes'] if response.status_code == 200 else None


@functools.lru_cache(maxsize=128)
def get_material(uri):

    url = "https://api.bsdd.buildingsmart.org/api/Class/v1"
    response = requests.get(url, {'Uri':uri, 'ClassType': 'Material'})
    return response.json() if response.status_code == 200 else None


@functools.lru_cache(maxsize=128)
def get_materials(uri):

    url = "https://api.bsdd.buildingsmart.org/api/Dictionary/v1/Classes"
    uri = uri.split("/class")[0]
    response = requests.get(url, {'Uri':uri, 'ClassType': 'Material'})
    return response.json()['classes'] if response.status_code == 200 else None


@functools.lru_cache(maxsize=128)
def get_properties(uri):

    url = "https://api.bsdd.buildingsmart.org/api/Dictionary/v1/Properties"
    uri = uri.split("/class")[0]
    response = requests.get(url, {'Uri':uri})
    return response.json()['properties'] if response.status_code == 200 else None


@functools.lru_cache(maxsize=128)
def find_property_by_uri(uri):

    url = "https://api.bsdd.buildingsmart.org/api/Property/v4"
    response = requests.get(url, {'uri': uri})
    return response.json() if response.status_code == 200 else None


def first_available_attr(object, properties):

    for prop in properties:

        #if prop in object.__dir__():
        if hasattr(object, prop): 
            return getattr(object, prop)
        
    return None


#TODO: exploratory code, needs some refactoring
def perform(file_name, task_id, verbose=False):
    
    ifc_file = ifcopenshell.open(file_name)   
    bsdd_results = {
        'dictionaries': [],
        'classes': [],
        'assignments': [],
        'properties': [],
        'materials': [],
        'messages': []
    }    
    
    ifc_file_classifications = ifc_file.by_type("IfcClassification")
    ifc_file_classification_references = ifc_file.by_type("IfcClassificationReference")
    ifc_file_rel_associates_classifications = ifc_file.by_type("IfcRelAssociatesClassification")
    ifc_file_properties = ifc_file.by_type("IfcProperty")
    ifc_file_property_sets = ifc_file.by_type("IfcPropertySet")
    ifc_file_materials = ifc_file.by_type("IfcMaterial")
    ifc_file_rel_associates_material = ifc_file.by_type("IfcRelAssociatesMaterial")

    # bSDD dictionary (former name: domain)
    # https://github.com/buildingSMART/bSDD/blob/master/Documentation/bSDD-IFC%20documentation.md#1-bsdd-dictionary
    if len(ifc_file_classifications):

        for _, ic in enumerate(ifc_file_classifications):

            logger.debug(f"File '{file_name}' for task_id = {task_id} has IfcClassification {ic.Name}.")

            dictionary_result = { 
                "dictionary_id": ic.id(),
                "dictionary_name": ic.Name,
                "dictionary_source": first_available_attr(ic, ['Specification', 'Location', 'Source']), # resp IFC 4.3 - IFC4 - IFC 2x3
                "dictionary_version": ic.Edition,
                "dictionary_owner": ic.Source,
                "dictionary_date": ic.EditionDate,
            }

            # lookup additional bSDD info
            if dictionary_result['dictionary_source'] is None:
                dictionary = find_dictionary_by_name(dictionary_result['dictionary_name'], dictionary_result['dictionary_version'])
                if not dictionary:
                    # not found
                    pass
                elif len(dictionary) == 1:
                    dictionary_result['dictionary_source'] = dictionary[0]['uri']
                elif len(dictionary) > 0:
                    # ambiguous reference
                    pass
        
            # exists in bSDD?
            dictionary_result['dictionary_uri'] = None
            dictionary_result['dictionary_in_bsdd'] = False
            if dictionary_result['dictionary_source']:
                dictionary = find_dictionary_by_uri(dictionary_result['dictionary_source'])
                if dictionary:
                    dictionary_result['dictionary_uri'] = dictionary['uri']
                    dictionary_result['dictionary_in_bsdd'] = True

            bsdd_results['dictionaries'] += [dictionary_result]

    # bSDD classes (former name: classification)
    # https://github.com/buildingSMART/bSDD/blob/master/Documentation/bSDD-IFC%20documentation.md#2-bsdd-classes-objects
    if len(ifc_file_classification_references):

        for _, icr in enumerate(ifc_file_classification_references):

            logger.debug(f"File '{file_name}' for task_id = {task_id} has IfcClassificationReference {icr.Name}.")

            class_result = { 
                "class_id": icr.id(),
                "class_name": icr.Name,
                "class_code": first_available_attr(icr, ['Identification', 'ItemReference']), # resp IFC 4.3/IFC4 - IFC 2x3
                "class_identifier": icr.Location,
                "parent_id": icr.ReferencedSource.id() if icr.ReferencedSource else None,
                "dictionary_id": None
            }

            # iterate parent until dictionary
            parent = icr.ReferencedSource
            while parent and parent.is_a() == 'IfcClassificationReference':
                parent = parent.ReferencedSource
            if parent and parent.is_a() == 'IfcClassification':
                class_result['dictionary_id'] = parent.id()

            # exists in bSDD?
            class_result['class_in_bsdd'] = False
            class_result['class_bsdd_uri'] = None
            class_result['class_bsdd_name'] = None
            if class_result['class_identifier']:
                class_ = get_class(class_result['class_identifier'])
                if class_:
                    class_result['class_in_bsdd'] = True
                    class_result['class_bsdd_uri'] = class_['uri']
                    class_result['class_bsdd_name'] = class_['name']
                    class_result['class_bsdd_rel_objects'] = class_['relatedIfcEntityNames'] if 'relatedIfcEntityNames' in class_ else None

            bsdd_results['classes'] += [class_result]

    if len(ifc_file_rel_associates_classifications):

        for _, rel in enumerate(ifc_file_rel_associates_classifications):

            logger.debug(f"File '{file_name}' for task_id = {task_id} has IfcRelAssociatesClassification {rel.Name}.")

            assignment_result = { 
                "assignment_id": rel.id(),
                "assignment_name": rel.Name,
                "assignment_description": rel.Description,
                "assignment_rel_objects": [],
                "assignment_rel_class": {
                    "id": rel.RelatingClassification.id(),
                    "type": rel.RelatingClassification.is_a(),
                }
            }
            for o in rel.RelatedObjects:
                assignment_result["assignment_rel_objects"] += [{
                    "id": o.id(),
                    "type": o.is_a()
                }]

            bsdd_results['assignments'] += [assignment_result]

    # bSDD properties
    # https://github.com/buildingSMART/bSDD/blob/master/Documentation/bSDD-IFC%20documentation.md#4-bsdd-properties
    if len(ifc_file_properties):

        for _, prop in enumerate(ifc_file_properties):

            logger.debug(f"File '{file_name}' for task_id = {task_id} has IfcProperty {prop.Name}.")

            property_result = { 
                "property_id": prop.id(),
                "property_type": prop.is_a(),
                "property_name": prop.Name,
                "property_identifier": first_available_attr(prop, ['Specification', 'Description']), # resp IFC 4.3 - IFC4/IFC 2x3
                "property_predefined_value": None,
                "property_predefined_type": None,
                "property_unit": prop.Unit if hasattr(prop, 'Unit') else None,
                "property_allowed_values": None,
            }

            # NominalValue
            if hasattr(prop, 'NominalValue') and prop.NominalValue:
                value = prop.NominalValue
                property_result["property_predefined_value"] = value.wrappedValue
                property_result["property_predefined_type"] = value.is_a()                

            # EnumerationValues
            if hasattr(prop, 'EnumerationValues') and prop.EnumerationValues:
                property_result["property_allowed_values"] = []
                for enum_value in prop.EnumerationValues:
                    property_result["property_allowed_values"] += [{
                        'value': enum_value.wrappedValue,
                        'type': enum_value.is_a()
                    }]

            # Unit
            if hasattr(prop, 'Unit') and prop.Unit and isinstance(prop.Unit, ifcopenshell.entity_instance):
                property_result["property_unit"] = prop.Unit.__str__()

            # exists in bSDD?
            property_result['property_uri'] = None
            property_result['property_in_bsdd'] = False
            property_result['property_bsdd_name'] = None
            property_result['property_bsdd_datatype'] = None
            property_result['property_bsdd_valuekind'] = None
            if property_result['property_identifier']:
                property = find_property_by_uri(property_result['property_identifier'])
                if property:
                    property_result['property_uri'] = property['uri']
                    property_result['property_in_bsdd'] = True
                    property_result['property_bsdd_name'] = property['name']
                    property_result['property_bsdd_datatype'] = property['dataType'] # Boolean, Character, Integer, Real, String, Time
                    property_result['property_bsdd_valuekind'] = property['propertyValueKind'] # Single, Range, List, Complex, ComplexList

            # TODO

            bsdd_results['properties'] += [property_result]

    # bSDD materials
    # https://github.com/buildingSMART/bSDD/blob/master/Documentation/bSDD-IFC%20documentation.md#3-bsdd-materials
    if len(ifc_file_materials):

        for _, mat in enumerate(ifc_file_materials):

            logger.debug(f"File '{file_name}' for task_id = {task_id} has IfcMaterial {mat.Name}.")

            material_result = { 
                "material_id": mat.id(),
                "material_name": mat.Name,
                "material_code": first_available_attr(mat, ['Identification', 'ItemReference']), # resp IFC 4.3/IFC4 - IFC 2x3
                #"material_identifier":  TODO - Location?
                "material_description": first_available_attr(mat, ['Description']), # IFC 4x only
            }

            # TODO

            bsdd_results['materials'] += [material_result]

    # Validation Rules
    #
    #   Categories:
    #     bSDD (top level)
    #     Dictionary
    #     Class
    #     Assignment
    #     Properties
    #     Materials

    # no dictionary or class references --> N/A
    if not len(ifc_file_classifications) and not len(ifc_file_classification_references):
        
        bsdd_results['messages'] += [{
            "rule": 1,
            "category": "bSDD",
            "severity": "N/A",
            "outcome": "Not Applicable",
            "message": "File doesn't reference any Dictionary/Classes.",
        }]

        print(json.dumps(bsdd_results))
        return

    # dictionary checks    
    for dictionary in bsdd_results['dictionaries']:

        # Check #2 - dictionary in bSDD --> Passed
        if dictionary['dictionary_in_bsdd']:

            bsdd_results['messages'] += [{
                "rule": 2,
                "category": "dictionary",
                "severity": "Passed",
                "outcome": "Passed",                
                "message": f"Dictionary '{dictionary['dictionary_name']}' with source '{dictionary['dictionary_source']}' exists in bSDD.",
                "dictionary": dictionary['dictionary_name'],
                "instance_id": dictionary['dictionary_id']
            }]
    
        # Check #3 - dictionary not in bSDD and not external --> Error    
        if not dictionary['dictionary_in_bsdd'] and dictionary['dictionary_source'] and 'buildingsmart.org' in dictionary['dictionary_source']:

            bsdd_results['messages'] += [{
                "rule": 3,
                "category": "dictionary",
                "severity": "Error",
                "outcome": "Reference Error",
                "message": f"Dictionary '{dictionary['dictionary_name']}' with source '{dictionary['dictionary_source']}' was not found in bSDD.",
                "dictionary": dictionary['dictionary_name'],
                "instance_id": dictionary['dictionary_id']
            }]

        # Check #4 - dictionary not in bSDD but external --> Neutral (Passed)
        if not dictionary['dictionary_in_bsdd'] and dictionary['dictionary_source'] and not 'buildingsmart.org' in dictionary['dictionary_source']:

            bsdd_results['messages'] += [{
                "rule": 4,
                "category": "dictionary",
                "severity": "Passed",
                "outcome": "Passed",
                "message": f"Dictionary '{dictionary['dictionary_name']}' with source '{dictionary['dictionary_source']}' was not found in bSDD, but is external.",
                "dictionary": dictionary['dictionary_name'],
                "instance_id": dictionary['dictionary_id']
            }]
    
        # Check #5 - dictionary uri does not start with https:// --> Warning
        if dictionary['dictionary_source'] and not dictionary['dictionary_source'].startswith('https://'):

            bsdd_results['messages'] += [{
                "rule": 5,
                "category": "dictionary",
                "severity": "Warning",
                "outcome": "Warning",
                "message": f"Dictionary source '{dictionary['dictionary_source']}' does not start with https:// .",
                "dictionary": dictionary['dictionary_name'],
                "instance_id": dictionary['dictionary_id']
            }]

        # Check #6 - dictionary uri contains a dash in front of the version --> Warning
        # TODO

        # Check #7 - duplicate bSDD dictionary references --> Warning
        # TODO

    # class checks
    for class_ in bsdd_results['classes']:
        
        # Check #10 - class in bSDD and same name --> Passed
        if class_['class_in_bsdd'] and class_['class_bsdd_name'] == class_['class_name']:

            bsdd_results['messages'] += [{
                "rule": 10,
                "category": "class",
                "severity": "Passed",
                "outcome": "Passed",
                "message": f"Class '{class_['class_name']}' with identifier '{class_['class_identifier']}' exists in bSDD.",
                "class": class_['class_name'],
                "instance_id": class_['class_id']
            }]

        # Check #11 - class in bSDD but different name --> Warning
        if class_['class_in_bsdd'] and class_['class_bsdd_name'] != class_['class_name']:

            bsdd_results['messages'] += [{
                "rule": 11,
                "category": "class",
                "severity": "Warning",
                "outcome": "Warning",
                "message": f"Class '{class_['class_name']}' with identifier '{class_['class_identifier']}' exists in bSDD, but with name '{class_['class_bsdd_name']}'.",
                "class": class_['class_name'],
                "instance_id": class_['class_id']
            }]

        # Check #12 - class not in bSDD and not external --> Error
        if not class_['class_in_bsdd'] and class_['class_identifier'] and 'buildingsmart.org' in class_['class_identifier']:

            bsdd_results['messages'] += [{
                "rule": 12,
                "category": "class",
                "severity": "Error",
                "outcome": "Reference Error",
                "message": f"Class '{class_['class_name']}' with identifier '{class_['class_identifier']}' was not found in bSDD.",
                "class": class_['class_name'],
                "instance_id": class_['class_id']
            }]

        # Check #13 - class not in bSDD but external --> Neutral (passed)
        if not class_['class_in_bsdd'] and class_['class_identifier'] and not 'buildingsmart.org' in class_['class_identifier']:

            bsdd_results['messages'] += [{
                "rule": 13,
                "category": "class",
                "severity": "Passed",
                "outcome": "Passed",
                "message": f"Class '{class_['class_name']}' with identifier '{class_['class_identifier']}' was not found in bSDD, but is external.",
                "class": class_['class_name'],
                "instance_id": class_['class_id']
            }]

        # Check #14 - class uri does not start with https:// --> Warning 
        if class_['class_identifier'] and not class_['class_identifier'].startswith('https://'):

            bsdd_results['messages'] += [{
                "rule": 14,
                "category": "class",
                "severity": "Warning",
                "outcome": "Warning",
                "message": f"Class identifier '{class_['class_identifier']}' does not start with https:// .",
                "class": class_['class_name'],
                "instance_id": class_['class_id']
            }]

        # Check #15 - class uri has dash before version 
        # TODO

    # relation constraint checks
    for assignment in bsdd_results['assignments']:

        rel_objects = assignment['assignment_rel_objects']
        rel_class = assignment['assignment_rel_class']
        class_ = [c for c in bsdd_results['classes'] if c['class_id'] == rel_class['id']]
        class_ = class_[0] if len(class_) > 0 else None

        # TODO - check with Artur re. IfcCommunication_s_Appliance --> confirmed, typo!
        if class_ and 'class_bsdd_rel_objects' in class_ and class_['class_bsdd_rel_objects']:
            for rel_object in rel_objects:

                if rel_object['type'] not in class_['class_bsdd_rel_objects']:

                    bsdd_results['messages'] += [{
                        "rule": 20,
                        "category": "assignment",
                        "severity": "Error",
                        "outcome": "Reference Error",
                        "message": f"'{class_['class_name']}' can't be used as '{rel_object['type']}' - allowed values: {class_['class_bsdd_rel_objects']}'.",
                        "instance_id": rel_object['id']
                    }]

                else:

                    bsdd_results['messages'] += [{
                        "rule": 11,
                        "category": "assignment",
                        "severity": "Passed",
                        "outcome": "Passed",
                        "message": f"'{class_['class_name']}' can be used as '{rel_object['type']}' - allowed values: {class_['class_bsdd_rel_objects']}'.",
                        "instance_id": rel_object['id']
                    }]

    # property checks
    for property in bsdd_results['properties']:

        # Check #30 - property in bSDD and same name --> Passed
        if property['property_in_bsdd'] and property['property_bsdd_name'] == property['property_name']:

            bsdd_results['messages'] += [{
                "rule": 30,
                "category": "property",
                "severity": "Passed",
                "outcome": "Passed",
                "message": f"Property '{property['property_name']}' with identifier '{property['property_identifier']}' exists in bSDD.",
                "property": property['property_name'],
                "instance_id": property['property_id']
            }]
        
        # Check #31 - property in bSDD but different name --> Warning
        if property['property_in_bsdd'] and property['property_bsdd_name'] != property['property_name']:

            bsdd_results['messages'] += [{
                "rule": 31,
                "category": "property",
                "severity": "Warning",
                "outcome": "Warning",
                "message": f"Property '{property['property_name']}' with identifier '{property['property_identifier']}' exists in bSDD, but with name '{property['property_bsdd_name']}'.",
                "property": property['property_name'],
                "instance_id": property['property_id']
            }]

        # Check #32 - property not in bSDD and not external --> Error
        if not property['property_in_bsdd'] and property['property_identifier'] and 'buildingsmart.org' in property['property_identifier']:

            bsdd_results['messages'] += [{
                "rule": 32,
                "category": "property",
                "severity": "Error",
                "outcome": "Reference Error",
                "message": f"Property '{property['property_name']}' with identifier '{property['property_identifier']}' was not found in bSDD.",
                "property": property['property_name'],
                "instance_id": property['property_id']
            }]

        # Check #33 - property not in bSDD but external --> Neutral (passed)
        if not property['property_in_bsdd'] and property['property_identifier'] and not 'buildingsmart.org' in property['property_identifier']:

            bsdd_results['messages'] += [{
                "rule": 33,
                "category": "property",
                "severity": "Passed",
                "outcome": "Passed",
                "message": f"Property '{property['property_name']}' with identifier '{property['property_identifier']}' was not found in bSDD, but is external.",
                "property": property['property_name'],
                "instance_id": property['property_id']
            }]

    # .... more property/material checks
    # etc...
    # TODO

    # Rule #99 - Passed when no other rule violations exist
    if not len(bsdd_results['messages']):

        bsdd_results['messages'] += [{            
            "rule": 99,
            "category": "bSDD",
            "severity": "Passed",
            "outcome": "Passed",
            "message": "All bSDD validations passed.",
            "instance_id": None
        }]

    if not verbose:
        bsdd_results['dictionaries'] = []
        bsdd_results['classes'] = []
        bsdd_results['assignments'] = []
        bsdd_results['properties'] = []
        bsdd_results['materials'] = []

    print(json.dumps(bsdd_results))
    sys.exit(0)


if __name__=="__main__":

    parser = argparse.ArgumentParser(description="Runs bSDD validation checks.")
    parser.add_argument("--file-name", "-f", type=str, required=True)
    parser.add_argument("--task-id", "-t", type=int, required=True)
    parser.add_argument("--verbose", "-v", action='store_true')
    args = parser.parse_args()

    perform(
        file_name=args.file_name,
        task_id=args.task_id,
        verbose=args.verbose
    )
