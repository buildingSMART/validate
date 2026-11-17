"""Request metadata and model validation states used by the HTML frontend."""
from dataclasses import dataclass
from datetime import datetime

from .report import CheckStatus, JSONValue


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelSummary:
    """Capture a request's file metadata and combined model states without ORM objects."""

    request_id: str
    file_name: str
    size_bytes: int
    created: datetime
    status: str
    progress: int | None
    header: dict[str, JSONValue]
    header_status: CheckStatus
    signatures_status: CheckStatus
    security_status: CheckStatus
    syntax_status: CheckStatus
    schema_status: CheckStatus
    normative_status: CheckStatus
    industry_status: CheckStatus
