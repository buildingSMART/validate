
import json
import re

from apps.ifc_validation_models.models import Model, ValidationOutcome
from .. import TaskContext, logger, with_model

STEP_ESCAPE_HINT = (
    "Non-ASCII characters are not allowed in a STEP physical file and must be "
    "encoded as \\X2\\..\\X0\\ escape sequences (ISO 10303-21)."
)

MAX_DISPLAY_LINE_LENGTH = 200

UNICODE_DECODE_ERROR_PATTERN = re.compile(
    r"UnicodeDecodeError: '[^']*' codec can't decode byte (0x[0-9a-fA-F]{2}) in position (\d+)"
)

# same comment pattern the simple_spf parser blanks out before tokenizing
COMMENT_PATTERN = re.compile(r"/\*[\s\S]*?\*/")


def format_annotated_line(line, column, display_line):
    if column > MAX_DISPLAY_LINE_LENGTH:
        # window the display around the column so the caret stays visible
        start = column - MAX_DISPLAY_LINE_LENGTH // 2
        display_line = "..." + display_line[start:start + MAX_DISPLAY_LINE_LENGTH]
        caret_offset = 3 + (column - 1 - start)
    else:
        display_line = display_line[:MAX_DISPLAY_LINE_LENGTH]
        caret_offset = column - 1
    return f"{line:05d} | {display_line}\n        {' ' * caret_offset}^"


def locate_byte_offset(file_path, offset):
    """Translate a byte offset into (line, column, display_line), reading the file in chunks."""
    try:
        line, last_newline_end, bytes_read = 1, 0, 0
        with open(file_path, "rb") as f:
            while bytes_read < offset:
                chunk = f.read(min(1 << 20, offset - bytes_read))
                if not chunk:
                    break
                line += chunk.count(b"\n")
                newline_at = chunk.rfind(b"\n")
                if newline_at != -1:
                    last_newline_end = bytes_read + newline_at + 1
                bytes_read += len(chunk)
            column = offset - last_newline_end + 1
            f.seek(last_newline_end)
            raw_line = f.read(max(column, MAX_DISPLAY_LINE_LENGTH) + 1).split(b"\n")[0]
        # latin-1 maps every byte to a character, so the offending line always renders
        return line, column, raw_line.decode("iso-8859-1")
    except OSError:
        return None


def locate_first_non_ascii(file_path):
    """Find the true position of the first non-ASCII character outside comments."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return None
    # blank out comments (preserving newlines) like the parser does: a non-ASCII
    # character inside a comment never reaches the tokenizer and is not an error
    blanked = COMMENT_PATTERN.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), content)
    match = re.search(r"[^\x00-\x7f]", blanked)
    if not match:
        return None
    line = blanked.count("\n", 0, match.start()) + 1
    line_start = blanked.rfind("\n", 0, match.start()) + 1
    column = match.start() - line_start + 1
    # blanking preserves length, so positions in `blanked` map 1:1 onto `content`
    line_end = content.find("\n", line_start)
    display_line = content[line_start:line_end if line_end != -1 else None]
    return line, column, display_line


def observed_from_error_output(error_output, file_path):
    """Build a user-facing message from subprocess stderr, which is never shown raw."""
    match = UNICODE_DECODE_ERROR_PATTERN.search(error_output)
    if match:
        byte, offset = match.group(1), int(match.group(2))
        located = locate_byte_offset(file_path, offset)
        if located:
            line, column, display_line = located
            return (f"On line {line} column {column}:\n"
                    f"File contains a non-ASCII byte ('{byte}'). {STEP_ESCAPE_HINT}\n"
                    f"{format_annotated_line(line, column, display_line)}")
        return f"File contains a non-ASCII byte ('{byte}') at offset {offset}. {STEP_ESCAPE_HINT}"
    return "The file could not be parsed as a STEP physical file (ISO 10303-21)."


def observed_from_syntax_message(msg, file_path):
    """Correct the parser's reported position for non-ASCII characters.

    The only_header parser reconstructs the header into a new string before parsing,
    so its line numbers can point at the wrong line; recompute from the actual file.
    """
    message = msg.get("message")
    if msg.get("type") != "unexpected_character":
        return message
    try:
        found_value = int(msg.get("found_value"), 16)
    except (TypeError, ValueError):
        return message
    if found_value < 0x80:
        return message
    located = locate_first_non_ascii(file_path)
    if not located:
        return message
    line, column, display_line = located
    return (f"On line {line} column {column}:\n"
            f"Unexpected character ('{msg.get('found_value')}')\n"
            f"{STEP_ESCAPE_HINT}\n"
            f"{format_annotated_line(line, column, display_line)}")


def process_syntax_outcomes(context:TaskContext):
    #todo - unify output for all task executions
    output, error_output, success = (context.result.get(k) for k in ("output", "error_output", "success"))

    # process
    with with_model(context.request.id) as model:
        status_field = context.config.status_field.name
        task = context.task
        if success:
            setattr(model, status_field, Model.Status.VALID)
            task.outcomes.create(
                severity=ValidationOutcome.OutcomeSeverity.PASSED,
                outcome_code=ValidationOutcome.ValidationOutcomeCode.PASSED,
                observed=output if output else None
            )
        elif error_output:
            setattr(model, status_field, Model.Status.INVALID)
            task.outcomes.create(
                severity=ValidationOutcome.OutcomeSeverity.ERROR,
                outcome_code=ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR,
                observed=observed_from_error_output(error_output, context.file_path)
            )
        else:
            for msg in json.loads(output):
                setattr(model, status_field, Model.Status.INVALID)
                task.outcomes.create(
                    severity=ValidationOutcome.OutcomeSeverity.ERROR,
                    outcome_code=ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR,
                    observed=observed_from_syntax_message(msg, context.file_path)
                )

        model.save(update_fields=[status_field])

        # return reason for logging
        return "No IFC syntax error(s)." if success else f"Found IFC syntax errors:\n\nConsole: \n{output}\n\nError: {error_output}"


def process_syntax(context:TaskContext):
    return process_syntax_outcomes(context)

def process_header_syntax(context:TaskContext):
    return process_syntax_outcomes(context)
