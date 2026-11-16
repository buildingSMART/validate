import sys
from pydantic import Field, field_validator, model_validator
from typing import Tuple, Any, Optional
from dateutil.parser import isoparse
import ifcopenshell
from ifcopenshell import validate, simple_spf
import re
from packaging.version import parse, InvalidVersion

import logging 
import io
import yaml
import os
from config import ConfiguredBaseModel


STEP_ESCAPE_PATTERN = re.compile(
        r"\\X2\\(?P<x2>(?:[0-9A-Fa-f]{4})+)\\X0\\"
        r"|\\X4\\(?P<x4>(?:[0-9A-Fa-f]{8})+)\\X0\\"
        r"|\\X\\(?P<x>[0-9A-Fa-f]{2})"
        r"|\\S\\(?P<s>.)"
        r"|\\P(?P<p>[A-I])\\"
        r"|\\(?P<backslash>\\)"
    )


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

    # one multi-line record per invalid attribute:
    #   Attribute '<name>' has invalid type:
    #       Expected: <type>
    #       Current value type: <type>
    pattern = re.compile(r"Attribute '(.+?)' has invalid type:\s*Expected: (.+?)\s*Current value type: (.+?)\s*$", re.MULTILINE)

    return [match.groups() for match in pattern.finditer(log_stream.getvalue())]


def add_validation_error(data, field, expected, observed):
    """
    Register a header policy violation on `data` (the attributes dict or `ValidationInfo.data`).
    The field name goes to validation_errors (unchanged behaviour); validation_details gets the
    matching explanation so the report can show what the policy expects vs. what the header declares.
    """
    data['validation_errors'].append(field)
    data['validation_details'].append({'field': field, 'expected': expected, 'observed': observed})


def raw_description(file):
    """The FILE_DESCRIPTION.description as declared in the file, for reporting."""
    description = file.mvd.description
    if isinstance(description, (tuple, list)):
        return ' '.join(str(item) for item in description)
    return description


def is_valid_iso8601(dt_str: str) -> bool:
    try:
        isoparse(dt_str)
        return True
    except ValueError:
        return False
    

def decode_ifc_step_string(value):
    """
    Decodes an ISO 10303-21 (STEP) encoded string into a clean Python Unicode string.
    Supports \\X2\\...\\X0\\, \\X4\\...\\X0\\, \\X\\, \\S\\, \\P?\\ and \\\\
    
    See: https://technical.buildingsmart.org/resources/ifcimplementationguidance/string-encoding
    """
    if not isinstance(value, str) or "\\" not in value:
        return value

    state = { "codepage": "iso-8859-1" }

    def replacer(match):
        gd = match.groupdict()
        
        # ordered by statistically most common ISO-10303-21 escape sequences
        if gd["x2"]:
            return bytes.fromhex(gd["x2"]).decode("utf-16-be", "replace")
        if gd["backslash"]:
            return "\\"
        if gd["x4"]:
            return bytes.fromhex(gd["x4"]).decode("utf-32-be", "replace")
        if gd["x"]:
            return bytes([int(gd["x"], 16)]).decode("iso-8859-1")
        if gd["s"]:
            return bytes([(ord(gd["s"]) + 128) & 0xFF]).decode(state["codepage"], "replace")
        if gd["p"]:
            state["codepage"] = f"iso-8859-{ord(gd['p']) - 64}" # 64 is ord('A') - 1
            return ""
            
        return ""

    # re.sub handles all non-matched text slicing and joining
    return STEP_ESCAPE_PATTERN.sub(replacer, value)


def validate_and_split_originating_system(attributes):
    # Define the pattern with literal spaces around the hyphen
    # pattern = re.compile(r"^([^ ]+) - (.+) - (\d+([.,;|]\d+)*)$")
    
    # matches symbols separated by: literal space - hypen - literal space 
    # using greedy (.+) to specify constraints on the subcategory (i.e. company name)
    pattern = re.compile(r"(.+) - (.+) - (.+)")

    try:
        match = pattern.match(attributes['originating_system'])
        if not match:
            add_validation_error(attributes, 'originating_system',
                                 'Software Company Name - Application Name - Application Version',
                                 attributes['originating_system'])
            company_name = application_name = version = None

        else:
            company_name, application_name, version = match.group(1), match.group(2), match.group(3)
    except TypeError:
        company_name = application_name = version = None
    
    attributes |= {
        'company_name': decode_ifc_step_string(company_name),
        'application_name': decode_ifc_step_string(application_name),
        'version': version,
    }
        
    return attributes


class HeaderStructure(ConfiguredBaseModel):
    file: Optional[simple_spf.file] = None
    validation_errors : list = Field(default_factory=list)  
    # one entry per validation error, in the same order: {'field', 'expected', 'observed'}
    validation_details : list = Field(default_factory=list)
    
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
    mvd: Optional[Any] = Field(default=None)  # Expected: ifcopenshell.util.mvd_info.AutoCommitList
    comments: Optional[Any] = Field(default=None)  # Expected: ifcopenshell.util.mvd_info.AutoCommitList
    
    
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
            attributes['validation_details'] = []
            attributes['mvd'] = file.mvd.view_definitions
            attributes['comments'] = file.mvd.comments
            attributes['schema_identifier'] = ''
            
            attributes = validate_and_split_originating_system(attributes)
            
            if file.mvd.description:
                for field, expected_type, observed_type in ifcopenshell_pre_validation(file):
                    add_validation_error(attributes, field, f'A value of type {expected_type}', observed_type)
                    attributes[field] = None

            values.update(attributes)         
        
        return values

    
    @field_validator('comments', mode='after')
    def validate_description(cls, v, values):
        """
        https://github.com/buildingSMART/IFC4.x-IF/tree/main/docs/IFC-file-header#description
        For grammar refer to https://standards.buildingsmart.org/documents/Implementation/ImplementationGuide_IFCHeaderData_Version_1.0.2.pdf
        """
        if v:            
            # comments is a free textfield, but constrainted to 256 characters
            if len(v) > 256:
                add_validation_error(values.data, values.field_name,
                                     'A comment of at most 256 characters',
                                     ', '.join(str(comment) for comment in v))
                return v if type(v) == tuple else v
            
            return v if type(v) == tuple else v
        return v


    @field_validator('mvd', mode='after')
    def validate_and_set_mvd(cls, v, values):
        """
        https://github.com/buildingSMART/IFC4.x-IF/tree/main/docs/IFC-file-header#description
        For grammar refer to https://standards.buildingsmart.org/documents/Implementation/ImplementationGuide_IFCHeaderData_Version_1.0.2.pdf
        This function runs after the other fields. It validates the mvd based on the grammar done in  
        the 'description' field. The function checks the constraints on the mvds and returns 
        the comma separated list into a single string.
        """
        if not v:
            add_validation_error(values.data, 'description',
                                 'One Model View Definition, declared as ViewDefinition [...]',
                                 raw_description(values.data.get('file')))
            return v

        allowed_descriptions = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), 'valid_descriptions.yaml')))
        schema_identifier = values.data.get('file').schema_identifier
        allowed_for_schema = allowed_descriptions.get(schema_identifier, [])
        
        view_definitions_set = {view for view in v} 

        if any("AddOnView" in view for view in view_definitions_set):
            if not any("CoordinationView" in view for view in view_definitions_set):
                add_validation_error(values.data, 'description',  # AddOnView MVD without CoordinationView
                                     'Add-on views only in combination with CoordinationView',
                                     raw_description(values.data.get('file')))
        
        for mvd in v:
            if mvd not in allowed_for_schema and not 'AddOnView' in mvd:
                add_validation_error(values.data, 'description',
                                     f"One of the MVDs valid for {schema_identifier}: {', '.join(allowed_for_schema)}"
                                     if allowed_for_schema else f'An MVD valid for {schema_identifier} (none defined)',
                                     mvd)

        # A header declares exactly one base MVD; add-on views don't count, the same name declared
        # twice counts twice. Names are stripped and add-ons matched case-insensitively for this
        # check only.
        base_views = [name for name in (view.strip() for view in v) if name and 'addonview' not in name.lower()]
        if len(base_views) > 1:
            add_validation_error(values.data, 'description',  # more than one base MVD
                                 'Exactly one base MVD (add-on views excluded)',
                                 ', '.join(base_views))
   
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
            add_validation_error(values.data, values.field_name,
                                 'A date and time in ISO 8601 format, e.g. 2022-11-21T05:33:05', v)
        return v
        
        
    @field_validator('company_name', 'application_name')
    def check_non_empty_fields(cls, v, values):
        # The only constraints so far is that the field: 
        # - must not be empty 
        # - must not contain dashes
        # - must not contain trailing and/or leading whitespaces
        if not (v and v == v.strip() and '-' not in v):
            part = 'Software Company Name' if values.field_name == 'company_name' else 'Application Name'
            add_validation_error(values.data, values.field_name,
                                 f'{part} from Originating System: not empty, no dashes, no leading or trailing whitespace', v)
        return v
    
    
    @field_validator('version')
    def validate_version(cls, v, values):
        if v:         
            try:
                parse(v)
                if v.strip() != v:
                    add_validation_error(values.data, values.field_name,
                                         'Application Version from Originating System: no leading or trailing whitespace', v)
            except InvalidVersion:
                add_validation_error(values.data, values.field_name,
                                     'Application Version from Originating System according to PEP 440: '
                                     'numbers and dots, optionally followed by -alpha, -beta or -rc', v)
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
    except ifcopenshell.simple_spf.CollectedValidationErrors:
        header = HeaderStructure(file=None, validation_errors=["syntax_error"])
    except Exception as e:
        print(f"Error opening file '{filename}': {e}")
        sys.exit(1)
    
    print(header.model_dump_json(exclude={'file'}))
    

if __name__ == '__main__':
    main()
