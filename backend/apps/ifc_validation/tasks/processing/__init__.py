from .instance_completion import process_instance_completion
from .gherkin import (
    process_gherkin_outcomes,
    process_normative_ia,
    process_normative_ip,
    process_prerequisites,
    process_industry_practices
)
from .syntax import process_syntax, process_header_syntax
from .schema import process_schema
from .header import process_header
from .digital_signatures import process_digital_signatures
from .bsdd import process_bsdd