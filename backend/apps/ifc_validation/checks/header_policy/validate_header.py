import sys
from pydantic import Field, field_validator, model_validator
from typing import Tuple, Union
import ifcopenshell
import yaml
import re
import os
import unicodedata

from config import ConfiguredBaseModel


class HeaderStructure(ConfiguredBaseModel):
    file: ifcopenshell.file
    validation_errors : list 
    
    description: Union[Tuple[str, ...], str] = Field(default_factory=tuple)
    implementation: str = Field(default="")
    name: str = Field(default="")
    time_stamp: str = Field(default="")
    author: Union[Tuple[str, ...], str] = Field(default_factory=tuple)
    organization: Union[Tuple[str, ...], str] = Field(default_factory=tuple)
    preprocessor_version: str = Field(default="")
    originating_system: str = Field(default="")
    authorization: str = Field(default="")
    
    
    @model_validator(mode='before')
    def populate_header(cls, values):
        if "file" in values:
            file = values["file"]
            header = file.wrapped_data.header
            file_description = header.file_description
            file_name = header.file_name
            values['description'] = getattr(file_description, 'description', ('',)) or ('',)
            values['implementation'] = getattr(file_description, 'implementation_level', "") or ''
            values['name'] = getattr(file_name, 'name', "") or ''
            values['time_stamp'] = getattr(file_name, 'time_stamp', "") or ''
            values['author'] = getattr(file_name, 'author', ('',)) or ('',)
            values['organization'] = getattr(file_name, 'organization', ('',)) or ('',)
            values['preprocessor_version'] = getattr(file_name, 'preprocessor_version', "") or ''
            values['originating_system'] = getattr(file_name, 'originating_system', "") or ''
            values['authorization'] = getattr(file_name, 'authorization', "") or ""
            
            values['validation_errors'] = []
            
            #check whether everything in string is in latin alphabet
            values['validation_errors'].extend(
                k for k, v in values.items() if k != "file" and not is_latin_string(recursive_unpack_value(v))
            )
        
        return values


    @field_validator('description')
    def validate_description(cls, v, values):
        # https://github.com/buildingSMART/IFC4.x-IF/tree/header-policy/docs/IFC-file-header#description
        v = recursive_unpack_value(v).replace(' ', '') # allow whitespaces
        allowed_descriptions = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), 'valid_descriptions.yaml')))
        
        schema_identifier = values.data.get('file').schema_identifier
        try:
            if not v in list(map(lambda desc: desc.replace(" ", ""), allowed_descriptions.get(schema_identifier))):
                values.data.get('validation_errors').append('description')
            if not v: # description field is mandatory
                values.data.get('validation_errors').append('description')
        except:
            pass  ## ---> what to do with invalid schema identifier? (IFC4X3)
        return v
    
    
    @field_validator('time_stamp')
    def validate_time_stamp(cls, v, values):
        iso8601_pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}T"            # Date part: YYYY-MM-DDT
        r"(?:[01]\d|2[0-3]):"             # Hour: 00-23
        r"[0-5]\d:"                       # Minutes: 00-59
        r"[0-5]\d"                        # Seconds: 00-59
        r"(?:\.\d+)?(?:Z|[+-][01]\d:[0-5]\d)?$"  # Optional fractional seconds and timezone
    )
        if iso8601_pattern.match(v):
            return v
        else:
            values.data.get('validation_errors').append('time_stamp')
            return v
        

    @field_validator('organization')
    def validate_organization(cls, v, values):
        v = recursive_unpack_value(v)
        if v.lower() == "unknown" or re.fullmatch(r"[a-zA-Z]+", v) or is_originating_system(v) or not v:
            values.data.get('validation_errors').append('organization')
            return v
        return v
    

    @field_validator('preprocessor_version')
    def validate_preprocessor_version(cls, v, values):
        """
        ^(?!None$): -> String is not exactly 'None'
        (?!Unknown$): -> String is not exactly 'Unknown'
        .*[a-zA-Z].*: -> At least one letter (upper or lowercase)
        .*\d.*: -> At least one digit
        .*$: -> Match rest of string
        """
        pattern = re.compile(r"^(?!None$)(?!Unknown$).*[a-zA-Z].*\d.*$", re.IGNORECASE)
        if not pattern.match(v) or is_originating_system(v): # check if it's not an originating_system value. Should we also check this for other fields?
            values.data.get('validation_errors').append('preprocessor_version')
            return v
        return v


    @field_validator('originating_system')
    def validate_originating_system(cls, v, values):
        """
        \s-\s: -> ' - ' separators
        [^-]+?: -> Software/application name between separators
        ([.,;|]\d+)*: -> Occurences of digits and separators (e.g. 26.0.0 or 26,0,0)
        """
        if not is_originating_system(v):
            values.data.get('validation_errors').append('originating_system')
            return v
        return v


def is_latin_string(s):
    for char in s:
        if not (char.isascii() or 
                unicodedata.name(char, "").startswith("LATIN")):
            return False
    return True

    
def is_originating_system(value):
    return re.compile(r"^[^-]+?\s-\s[^-]+?\s-\s\d+([.,;|]\d+)*$").match(value)


def recursive_unpack_value(item):
    if isinstance(item, tuple):
        if len(item) == 0:
            return None
        elif len(item) == 1 or not item[0]:
            return recursive_unpack_value(item[1]) if len(item) > 1 else recursive_unpack_value(item[0])
        else:
            return item[0]
    return item


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
