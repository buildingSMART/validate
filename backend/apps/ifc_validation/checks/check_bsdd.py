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

    """
    Retrieves a Dictionary (aka Domain or Class System) matching a Uri within the bSDD online service.

    In bSDD, a dictionary is a standardised collection of object definitions, properties, and materials owned and maintained by one organisation.
    
    Mandatory Args:
        uri: Uri (or first part of the Uri) of the Dictionary.

    Returns:
        Json object representing the Dictionary, or None if none matches.

    See:
        https://github.com/buildingSMART/bSDD/blob/master/Documentation/bSDD-IFC%20documentation.md#1.-bSDD-dictionary
        https://app.swaggerhub.com/apis/buildingSMART/Dictionaries/v1
    """

    url = "https://api.bsdd.buildingsmart.org/api/Dictionary/v1"

    response = requests.get(url, {'uri': uri })
    logger.debug(f'GET {response.url} returned HTTP {response.status_code}')

    if response.status_code == 200:
        json = response.json()
        return json['dictionaries'][0] if json['count'] == 1 else None # should actually return 404...
    elif response.status_code == 404:
        return None
    else:
        response.raise_for_status()
        return None
    

@functools.lru_cache(maxsize=128)
def get_all_dictionaries():
    
    """
    Retrieves all Dictionaries (aka Domains or Class Systems) within the bSDD online service.

    In bSDD, a dictionary is a standardised collection of object definitions, properties, and materials owned and maintained by one organisation.
    
    Returns:
        Json object collection representing all Dictionaries (including Test Dictionaries), or None if none exist.

    See:
        https://github.com/buildingSMART/bSDD/blob/master/Documentation/bSDD-IFC%20documentation.md#1.-bSDD-dictionary
        https://app.swaggerhub.com/apis/buildingSMART/Dictionaries/v1
    """

    url = "https://api.bsdd.buildingsmart.org/api/Dictionary/v1?includeTestDictionaries=True"
    
    dictionaries = []
    count = 0
    total_count = 1000
    
    while count < total_count:
        response = requests.get(url + f'&offset={count}&limit=250')
        logger.debug(f'GET {response.url} returned HTTP {response.status_code}')
        response.raise_for_status()

        json = response.json()
        dictionaries += json['dictionaries']
        total_count = json['totalCount']
        count = json['count']
    
    return dictionaries


@functools.lru_cache(maxsize=128)
def find_dictionary_by_name(name, edition = None):

    """
    Retrieves a Dictionary (aka Domain or Class System) matching a specific Name (and optionally Edition) within the bSDD online service.

    In bSDD, a dictionary is a standardised collection of object definitions, properties, and materials owned and maintained by one organisation.
    
    Mandatory Args:
        name: name of the Dictionary.

    Optional Args:
        edition: version of the Dictionary.

    Returns:
        Json objects representing the matching Dictionary/-ies, or None if none match.

    See:
        https://github.com/buildingSMART/bSDD/blob/master/Documentation/bSDD-IFC%20documentation.md#1.-bSDD-dictionary
        https://app.swaggerhub.com/apis/buildingSMART/Dictionaries/v1
    """

    all_dictionaries = get_all_dictionaries()
    dict_filter = lambda x: x['name'] == name and (edition is None or x['version'] == edition)
    return next((d for d in all_dictionaries if dict_filter(d)), None)


@functools.lru_cache(maxsize=128)
def find_class_by_uri(uri):

    """
    Retrieves Classes (aka Classification) matching a Uri within the bSDD online service.

    In bSDD, a class can be any (abstract) object (e.g. IfcWall), abstract concept (e.g. Costing) or process (e.g. Installation).
    
    Mandatory Args:
        uri: Uri (or first part of the Uri) of the Class.

    Returns:
        Json object representing the Classes, or None if none match.

    See:
        https://github.com/buildingSMART/bSDD/blob/master/Documentation/bSDD-IFC%20documentation.md#2-bsdd-classes-objects
        https://app.swaggerhub.com/apis/buildingSMART/Dictionaries/v1#/Class/get_api_Class_v1
    """

    url = "https://api.bsdd.buildingsmart.org/api/Class/v1"

    response = requests.get(url, {'uri':uri})
    logger.debug(f'GET {response.url} returned HTTP {response.status_code}')

    if response.status_code == 200:
        return response.json()
    elif response.status_code in (400, 404): # should actually return 404...
        return None
    else:
        response.raise_for_status()
        return None


@functools.lru_cache(maxsize=128)
def find_property_by_uri(uri):

    """
    Retrieves Properties matching a Uri within the bSDD online service.

    In bSDD, a class (object) can have multiple properties, and a property can be part of many classes (objects).
    
    Mandatory Args:
        uri: Uri (or first part of the Uri) of the Properties.

    Returns:
        Json object representing the Properties, or None if none match.

    See:
        https://github.com/buildingSMART/bSDD/blob/master/Documentation/bSDD-IFC%20documentation.md#4-bsdd-properties
        https://app.swaggerhub.com/apis/buildingSMART/Dictionaries/v1#/Property/get_api_Property_v4
    """

    url = "https://api.bsdd.buildingsmart.org/api/Property/v4"

    response = requests.get(url, {'uri': uri})
    logger.debug(f'GET {response.url} returned HTTP {response.status_code}')

    if response.status_code == 200:
        return response.json()
    elif response.status_code in (400, 404): # should actually return 404...
        return None
    else:
        response.raise_for_status()
        return None
    
    
def get_attr_safe(object, attribute):

    try:
        if hasattr(object, attribute): 
            return getattr(object, attribute)
    except RuntimeError: # ifcopenshell
        pass

    return None


def first_available_attr(object, attributes):

    for attr in attributes:

        if hasattr(object, attr): 
            return getattr(object, attr)
        
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

    ifc_file_rel_associates_classifications = ifc_file.by_type("IfcRelAssociatesClassification")
    ifc_file_properties = ifc_file.by_type("IfcProperty")
    #ifc_file_property_sets = ifc_file.by_type("IfcPropertySet")
    ifc_file_materials = ifc_file.by_type("IfcMaterial")
    #ifc_file_rel_associates_material = ifc_file.by_type("IfcRelAssociatesMaterial")

    # bSDD dictionary (former name: domain)
    # https://github.com/buildingSMART/bSDD/blob/master/Documentation/bSDD-IFC%20documentation.md#1-bsdd-dictionary
    if len(ifc_file_classifications):

        for ic in ifc_file_classifications:

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

        for icr in ifc_file_classification_references:

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
                class_ = find_class_by_uri(class_result['class_identifier'])
                if class_:
                    class_result['class_in_bsdd'] = True
                    class_result['class_bsdd_uri'] = class_['uri']
                    class_result['class_bsdd_name'] = class_['name']
                    class_result['class_bsdd_rel_objects'] = class_['relatedIfcEntityNames'] if 'relatedIfcEntityNames' in class_ else None

            bsdd_results['classes'] += [class_result]

    if len(ifc_file_rel_associates_classifications):

        for rel in ifc_file_rel_associates_classifications:

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

        for prop in ifc_file_properties:

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
            if get_attr_safe(prop, 'NominalValue'):
                value = prop.NominalValue
                if hasattr(value, 'wrappedValue'):
                    property_result["property_predefined_value"] = value.wrappedValue
                    property_result["property_predefined_type"] = value.is_a()
                elif value:
                    property_result["property_predefined_value"] = str(value)
                    property_result["property_predefined_type"] = str(type(value))

            # EnumerationValues
            if get_attr_safe(prop, 'EnumerationValues'):
                property_result["property_allowed_values"] = []
                for enum_value in prop.EnumerationValues:
                    if hasattr(enum_value, 'wrappedValue'):
                        property_result["property_allowed_values"] += [{
                            'value': enum_value.wrappedValue,
                            'type': enum_value.is_a()
                        }]
                    elif enum_value:
                        property_result["property_allowed_values"] += [{
                            'value': str(enum_value),
                            'type': str(type(enum_value))
                        }]

            # Unit
            if get_attr_safe(prop, 'Unit') and isinstance(prop.Unit, ifcopenshell.entity_instance):
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

        for mat in ifc_file_materials:

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
        bsdd_results['dictionaries'] = None
        bsdd_results['classes'] = None
        bsdd_results['assignments'] = None
        bsdd_results['properties'] = None
        bsdd_results['materials'] = None

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
