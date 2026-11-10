"""HTML presentation only: labels, fixed metadata rows and rule-value markup."""
import json

from django import template
from django.template.loader import render_to_string

from ..datamodel.report import (
    AlignmentMeasurement, AllowedValues, AttributeValue, EntityReference, GuidCharacters,
    GuidLength, InstanceReference, SchemaIdentifier, UnrecognizedValue,
)

register = template.Library()


@register.filter
def severity_label(value):
    return {0: "N/A", 1: "Applicable", 2: "Passed", 3: "Warning", 4: "Error"}[value]


@register.filter
def status_label(value):
    return {"v": "Valid", "i": "Invalid", "n": "N/A", "w": "Warning", "p": "Pending...", "-": "N/A"}[value]


@register.filter
def pdf_status_label(value):
    return {"v": "Valid", "i": "Invalid", "n": "Not validated", "w": "Warning", "p": "Pending", "-": "Not applicable"}[value]


@register.filter
def conformance_label(value):
    return {'v': 'No issues recorded', 'i': 'Errors found', 'w': 'Warnings recorded', 'n': 'Validation incomplete'}[value]


@register.filter
def signature_label(value):
    return {'invalid': 'Invalid signature', 'valid_unknown_cert': 'Valid signature · unknown certificate',
            'valid_known_cert': 'Valid signature · known certificate'}.get(value, value.replace('_', ' ').capitalize())


@register.simple_tag
def rule_value(value):
    templates = {
        AttributeValue: "attribute", AllowedValues: "choices", EntityReference: "entity",
        InstanceReference: "instance", SchemaIdentifier: "schema", GuidCharacters: "guid_characters",
        GuidLength: "guid_length", AlignmentMeasurement: "measurement", UnrecognizedValue: "unknown",
    }
    name = templates.get(type(value), "literal")
    literal_text = json.dumps(value) if isinstance(value, (bool, int, float)) else None
    return render_to_string(f"report/values/{name}.html", {"value": value, "literal_text": literal_text})


@register.filter
def scalar_text(value):
    # React does not print boolean children, even inside an AttributeValue.
    return "" if isinstance(value, bool) else str(value)


@register.inclusion_tag("report/header_row.html", takes_context=True)
def header_row(context, header, field, label, value, tooltip=""):
    return dict(label=label, value=value, tooltip=tooltip, invalid=field in header.invalid_fields,
                pdf=context.get('pdf', False),
                url=f"https://github.com/buildingSMART/IFC4.x-IF/tree/main/docs/IFC-file-header#{field}")


@register.inclusion_tag("report/signature_row.html")
def signature_row(label, value):
    return {"label": label, "value": value}


@register.simple_tag
def rule_export(group):
    """Text export uses the same value templates and selected rows as the table."""
    from html import unescape
    from django.utils.html import strip_tags

    def text(value):
        if isinstance(value, AllowedValues):
            return ", ".join(value.values)
        return unescape(strip_tags(rule_value(value))).strip()

    columns = ["Severity", "Id", "Entity", "Expected", "Observed"]
    if group.show_source:
        columns.extend(("Line", "Source"))
    rows = [group.title, "", "\t".join(columns)]
    for result in group.results:
        instance = result.instance
        row = [severity_label(result.severity_after_whitelisting), f"#{instance.step_id}" if instance else "-",
               instance.entity if instance else "-", text(result.expected), text(result.observed)]
        if group.show_source:
            source = instance.source if instance else None
            row.extend((str(source.line_number) if source else "-", source.statement if source else "-"))
        rows.append("\t".join(row))
    return "\n".join(rows)
