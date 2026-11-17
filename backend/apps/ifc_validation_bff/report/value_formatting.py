from __future__ import annotations

import json
import re

from ..datamodel.report import (
    AlignmentMeasurement, AllowedValues, AttributeValue, EntityReference,
    GuidCharacters, GuidLength, InstanceReference, JSONValue, GherkinValue,
    SchemaIdentifier, UnrecognizedValue,
)


def coerce_to_text(value: JSONValue) -> str:
    if not (isinstance(value, (tuple, list)) or value):
        return ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def interpret_rule_value(value: JSONValue) -> GherkinValue:
    """
    Interpret a structured JSON value in the expected/observed columns into a corresponding dataclass for rendering in the templates.
    """
    if not (isinstance(value, (tuple, list)) or value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        match value:
            case {"invalid_guid_chars": chars, "expected_or_observed": side}:
                chars = ",".join(map(str, chars)) if isinstance(chars, list) else str(chars)
                return GuidCharacters(chars, side == "expected", value.get("inst"))
            case {"length": int(length), "expected_or_observed": side}:
                return GuidLength(length, side == "expected", value.get("inst"))
            case {"value": inner}:
                return AttributeValue(inner) if isinstance(inner, (str, int, float, bool)) else interpret_rule_value(inner)
            case {"instance": str(description)}:
                return InstanceReference(description)
            case {"entity": str(name)}:
                return EntityReference(name.split("(#")[0])
            case {"oneOf": list(choices)}:
                return AllowedValues(tuple(map(str, choices)), value.get("context"))
            case {"schema_identifier": str(identifier)}:
                return SchemaIdentifier(tuple(identifier.split("\n")))
            case {"num_digits": int(digits)}:
                return measurement(value, digits)
    return UnrecognizedValue(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def measurement(value: dict[str, JSONValue], digits: int) -> AlignmentMeasurement:
    context = value.get("context") or ""
    label = f"{context[:1].upper()}{context[1:]} :" if context else "One of:"
    reported = value.get("expected") or value.get("observed")
    if isinstance(reported, list):
        display = "".join(map(str, reported))
        if label == "Position :":
            display = f"({reported[0]}, {reported[1]})"
    else:
        try:
            display = re.sub(r"e([+-])0+(\d+)$", r"e\1\2", f"{float(reported):.{digits}e}")
        except (TypeError, ValueError):
            display = str(reported)
    details = value.get("continuity_details")
    if not isinstance(details, dict):
        return AlignmentMeasurement(f"{label} {display}", ())

    def endpoint(segment: str, point: str, direction: str, prefix: str) -> tuple[str, ...]:
        coordinates = details.get(point) or (None, None)
        lines = (f"{prefix} {details.get(segment)}", f"Coords: ({coordinates[0]}, {coordinates[1]})")
        direction_label = "Tangent Direction" if "direction" in context else "Gradient" if "gradient" in context else None
        return (*lines, f"{direction_label}: {details.get(direction)}") if direction_label else lines

    return AlignmentMeasurement(f"{label} {display}", (
        *endpoint("segment_to_analyze", "current_end_point", "current_end_direction", "at end of"),
        *endpoint("following_segment", "following_start_point", "following_start_direction", "and start of"),
    ))


def pretty_file_size(size: int) -> str:
    amount = size / 1024
    units = iter(("kB", "MB", "GB", "TB"))
    unit = next(units)
    while amount > 1024:
        amount /= 1024
        unit = next(units, "TB")
    return f"{max(amount, 0.01):.2f} {unit}"


def outer_whitespace(value: str | None) -> str:
    return re.sub(r"^\s+|\s+$", lambda match: "□" * len(match[0]), value or "")


def truncate(value: str, limit: int = 64) -> str:
    return value[:limit - 3] + "..." if len(value) > limit else value
