import sys
from pydantic import Field, field_validator, model_validator
from typing import Tuple, Union, Optional
import ifcopenshell
from ifcopenshell import validate, SchemaError, simple_spf
import re
from datetime import datetime
from packaging.version import parse, InvalidVersion

import logging 
import io
import yaml
import os
from config import ConfiguredBaseModel


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

    try:
        match = pattern.match(attributes['originating_system'])
        if not match:
            attributes['validation_errors'].append('originating_system')
            company_name = application_name = version = None

        else:
            company_name, application_name, version = match.group(1), match.group(2), match.group(3)
    except TypeError:
        company_name = application_name = version = None
    
    attributes |= {
        'company_name': company_name,
        'application_name': application_name,
        'version': version,
    }
        
    return attributes


class HeaderStructure(ConfiguredBaseModel):
    file: Union[ifcopenshell.file, simple_spf.file]
    validation_errors : list = Field(default_factory=list)  
    
    description: Optional[Tuple[str, ...]] = Field(default=None)
    implementation: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    time_stamp: Optional[str] = Field(default=None)
    author: Optional[Tuple[str, ...]] = Field(default=None)
    organization: Optional[Tuple[str, ...]] = Field(default=None)
    preprocessor_version: Optional[str] = Field(default=None)
    originating_system: Optional[str] = Field(default=None)
    authorization: Optional[str] = Field(default=None)
    
    company_name: Optional[str] = Field(default=None)
    application_name: Optional[str] = Field(default=None)
    schema_identifier: Optional[str] = Field(default=None)
    version: Optional[str] = Field(default=None)
    mvd: Optional[ifcopenshell.util.mvd_info.AutoCommitList] = Field(default=None)
    comments: Optional[ifcopenshell.util.mvd_info.AutoCommitList] = Field(default=None)
    
    
    @model_validator(mode='before')
    def populate_header(cls, values):
        if (file := values.get('file')):

            header = file.header
            file_description = header.file_description
            file_name = header.file_name
            
            fields = [
                (file_description, 'implementation_level', 1),
                (file_name, 'name', 0),
                (file_name, 'time_stamp', 1),
                (file_name, 'author', 2),
                (file_name, 'organization', 3),
                (file_name, 'preprocessor_version', 4),
                (file_name, 'originating_system', 5),
                (file_name, 'authorization', 6)
            ]

            attributes = {field: getattr(obj, field) for obj, field, index in fields}
            
            attributes['validation_errors'] = []
            attributes['mvd'] = file.mvd.view_definitions
            attributes['comments'] = file.mvd.comments
            attributes['schema_identifier'] = ''
            
            attributes = validate_and_split_originating_system(attributes)
            
            if file.mvd.description:
                errors_from_pre_validation = ifcopenshell_pre_validation(file)
                for error in errors_from_pre_validation:
                    attributes['validation_errors'].append(error)
                    attributes[error] = None

            values.update(attributes)         
        
        return values

    
    @field_validator('comments', mode='after')
    def validate_description(cls, v, values):
        """
        https://github.com/buildingSMART/IFC4.x-IF/tree/header-policy/docs/IFC-file-header#description
        For grammar refer to https://standards.buildingsmart.org/documents/Implementation/ImplementationGuide_IFCHeaderData_Version_1.0.2.pdf
        """
        if v:            
            # comments is a free textfield, but constrainted to 256 characters
            if len(v) > 256:
                values.data.get('validation_errors').append(values.field_name)
                return v if type(v) == tuple else v
            
            return v if type(v) == tuple else v
        return v


    @field_validator('mvd', mode='after')
    def validate_and_set_mvd(cls, v, values):
        """
        https://github.com/buildingSMART/IFC4.x-IF/tree/header-policy/docs/IFC-file-header#description
        For grammar refer to https://standards.buildingsmart.org/documents/Implementation/ImplementationGuide_IFCHeaderData_Version_1.0.2.pdf
        This function runs after the other fields. It validates the mvd based on the grammar done in  
        the 'description' field. The function checks the constraints on the mvds and returns 
        the comma separated list into a single string.
        """
        if not v:
            values.data.get('validation_errors').append('description')
            return v

        allowed_descriptions = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), 'valid_descriptions.yaml')))
        schema_identifier = values.data.get('file').schema_identifier
        
        view_definitions_set = {view for view in v} 

        if any("AddOnView" in view for view in view_definitions_set):
            if not any("CoordinationView" in view for view in view_definitions_set):
                values.data.get('validation_errors').append('description')  # AddOnView MVD without CoordinationView        
        
        for mvd in v:
            if mvd not in allowed_descriptions.get(schema_identifier, [False]) and not 'AddOnView' in mvd:
                values.data.get('validation_errors').append('description')
   
        return ', '.join(v)
    
    
    @field_validator('time_stamp')
    def validate_time_stamp(cls, v, values):
        iso8601_pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}T"            # Date part: YYYY-MM-DDT
        r"(?:[01]\d|2[0-3]):"             # Hour: 00-23
        r"[0-5]\d:"                       # Minutes: 00-59
        r"[0-5]\d"                        # Seconds: 00-59
        r"(?:\.\d+)?(?:Z|[+-][01]\d:[0-5]\d)?$"  # Optional fractional seconds and timezone
    )   
        if not v or not (iso8601_pattern.match(v) and is_valid_iso8601(v)):
            values.data['validation_errors'].append(values.field_name)
        return v

        
        
    @field_validator('company_name', 'application_name')
    def check_non_empty_fields(cls, v, values):
        # The only constraint so far is that the field must not be empty and not contain dashes
        if not v or v.strip() == "" or '-' in v:
            values.data['validation_errors'].append(values.field_name)
        return v
    
    
    @field_validator('version')
    def validate_version(cls, v, values):
        if v:         
            try:
                parse(v)
            except InvalidVersion:
                values.data['validation_errors'].append(values.field_name)
        return v

    @field_validator('schema_identifier')
    def store_schema(cls, v, values):
        # schema is further validated in gherkin IFC101
        return values.data.get('file').schema_identifier
    

def main():
    if len(sys.argv) != 2:
        print("Usage: python -m validate_header <path_to_ifc_file>")
        sys.exit(1)

    filename = sys.argv[1] 
    try:
        file = ifcopenshell.simple_spf.open(filename, only_header=True)
        header = HeaderStructure(file=file)
    except Exception as e:
        print(f"Error opening file '{filename}': {e}")
        sys.exit(1)
    
    print(header.model_dump_json(exclude={'file'}))
    

if __name__ == '__main__':
    main()
