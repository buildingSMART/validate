import sys
from pydantic import Field, field_validator, model_validator
from typing import Tuple, Union
import ifcopenshell
from ifcopenshell import validate
import yaml
import re
import os
from datetime import datetime
from packaging.version import parse, InvalidVersion

import logging 
import io
from contextlib import redirect_stdout
from config import ConfiguredBaseModel
from mvd_parser import parse_mvd


def ifcopenshell_pre_validation(file):
    log_stream = io.StringIO()
    
    logger = logging.getLogger("local_ifcopenshell_logger")
    logger.setLevel(logging.DEBUG)  
    
    if logger.hasHandlers():
        logger.handlers.clear()
    
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

    validate.validate_ifc_header(file, logger)
    
    log_contents = log_stream.getvalue().strip().split('\n') 
    extracted_info = []
    
    pattern = r"Attribute '(.+?)' has invalid"
    
    for line in log_contents:
        match = re.search(pattern, line)
        if match:
            extracted_info.append(match.group(1))
    
    return extracted_info


def is_valid_iso8601(dt_str: str) -> bool:
    try:
        datetime.fromisoformat(dt_str)
        return True
    except ValueError:
        return False
    

def validate_and_split_originating_system(attributes):
    # Define the pattern with literal spaces around the hyphen
    # pattern = re.compile(r"^([^ ]+) - (.+) - (\d+([.,;|]\d+)*)$")
    
    # matches symbols separated by: literal space - hypen - literal space 
    # using greedy (.+) to specify constraints on the subcategory (i.e. company name)
    pattern = re.compile(r"(.+) - (.+) - (.+)")

    match = pattern.match(attributes['originating_system'])
    if not match:
        attributes['validation_errors'].append('originating_system')
        company_name = application_name = version = 'Not Defined'

    else:
        company_name, application_name, version = match.group(1), match.group(2), match.group(3)
        
    attributes['company_name'] = company_name
    attributes['application_name'] = application_name
    attributes['version'] = version
    
    return attributes


class HeaderStructure(ConfiguredBaseModel):
    file: ifcopenshell.file
    validation_errors : list 
    
    description: Tuple[str, ...] = Field(default_factory=tuple)
    implementation: str = Field(default="")
    name: str = Field(default="")
    time_stamp: str = Field(default="")
    author: Tuple[str, ...] = Field(default_factory=tuple)
    organization: Tuple[str, ...] = Field(default_factory=tuple)
    preprocessor_version: str = Field(default="")
    originating_system: str = Field(default="")
    authorization: str = Field(default="")
    
    company_name: str = Field(default="")
    application_name: str = Field(default="")
    version: str = Field(default="")
    
    
    @model_validator(mode='before')
    def populate_header(cls, values):
        if (file := values.get('file')):

            header = file.wrapped_data.header
            file_description = header.file_description
            file_name = header.file_name
            
            attributes = {
                'description': file_description.description,
                'implementation': file_description.implementation_level,
                'name': file_name.name,
                'time_stamp': file_name.time_stamp,
                'author': file_name.author,
                'organization': file_name.organization,
                'preprocessor_version': file_name.preprocessor_version,
                'originating_system': file_name.originating_system,
                'authorization': file_name.authorization, 
                'validation_errors' : []
            }
            
            attributes = validate_and_split_originating_system(attributes)
            
            errors_from_pre_validation = ifcopenshell_pre_validation(file)
            for error in errors_from_pre_validation:
                attributes['validation_errors'].append(error)
                attributes[error] = "Not Defined" if cls.__annotations__[error] == str else ('Not defined',)
            
            values.update(attributes)
                    
        
        return values


    @field_validator('description')
    def validate_description(cls, v, values):
        """
        https://github.com/buildingSMART/IFC4.x-IF/tree/header-policy/docs/IFC-file-header#description
        For grammar refer to https://standards.buildingsmart.org/documents/Implementation/ImplementationGuide_IFCHeaderData_Version_1.0.2.pdf
        """
        header_description_text = ' '.join(v)
        try:
            parsed_description = parse_mvd(header_description_text)
        except:
            pass
        view_definitions = parsed_description.mvd
        
        if not view_definitions:
            values.data.get('validation_errors').append(values.field_name)
            return v if type(v) == tuple else v

        
        if view_definitions == 'Not defined':
            values.data.get('validation_errors').append(values.field_name)
            return v if type(v) == tuple else v

        
        if values.data.get('file').schema_identifier == 'IFC4X3_ADD2':
            view_definitions_previous_versions = {
                'StructuralAnalysisView',
                'SpaceBoundaryAddonView',
                'BasicFMHandoverView',
                'ReferenceView_V1.2',
                'IFC4Precast'
            }
            if set(view_definitions) & view_definitions_previous_versions:
                values.data.get('validation_errors').append(values.field_name)
                return v if type(v) == tuple else v

        
        # comments is a free textfield, but constrainted to 256 characters
        if len(parsed_description.comments) > 256:
            values.data.get('validation_errors').append(values.field_name)
            return v if type(v) == tuple else v

        
        # AddonViews cannot be used without CoordinationView.
        view_definitions_lowercase = {mvd.lower() for mvd in view_definitions}
        if any('addonview' in mvd for mvd in view_definitions_lowercase) and 'coordinationview' not in view_definitions_lowercase:
            values.data.get('validation_errors').append(values.field_name)
            return v if type(v) == tuple else v

            
        # anything besides exactly CoordinationView as a single item gets excluded
        if len(view_definitions) == 1 and view_definitions[0].lower() != 'coordinationview':
            values.data.get('validation_errors').append(values.field_name)
            return v if type(v) == tuple else v

        
        return v if type(v) == tuple else v

    
    
    @field_validator('time_stamp')
    def validate_time_stamp(cls, v, values):
        iso8601_pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}T"            # Date part: YYYY-MM-DDT
        r"(?:[01]\d|2[0-3]):"             # Hour: 00-23
        r"[0-5]\d:"                       # Minutes: 00-59
        r"[0-5]\d"                        # Seconds: 00-59
        r"(?:\.\d+)?(?:Z|[+-][01]\d:[0-5]\d)?$"  # Optional fractional seconds and timezone
    )
        if iso8601_pattern.match(v) and is_valid_iso8601(v):
            return v
        else:
            values.data.get('validation_errors').append(values.field_name)
            return v
        
        
    @field_validator('company_name', 'application_name')
    def check_non_empty_fields(cls, v, values):
        # The only constraint so far is that the field must not be empty and not contain dashes
        if v.strip() == "" or '-' in v:
            values.data['validation_errors'].append(values.field_name)
        return v
    
    
    @field_validator('version')
    def validate_version(cls, v, values):
        if v.lower() != 'not defined': # in this case, there is already an error for originating_system       
            try:
                parse(v)
            except InvalidVersion:
                values.data['validation_errors'].append(values.field_name)
        return v
    

def main():
    if len(sys.argv) != 2:
        print("Usage: python -m validate_header <path_to_ifc_file>")
        sys.exit(1)

    filename = sys.argv[1] 
    try:
        file = ifcopenshell.open(filename)
    except Exception as e:
        print(f"Error opening file '{filename}': {e}")
        sys.exit(1)

    header = HeaderStructure(file=file)
    
    print(header.model_dump_json(exclude={'file'}))
    

if __name__ == '__main__':
    main()
