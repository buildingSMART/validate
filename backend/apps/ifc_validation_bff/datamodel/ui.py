"""Page content and interaction state. No ORM objects, JSON payloads or cell types."""
from dataclasses import dataclass
from datetime import datetime

from .report import CheckStatus


@dataclass(frozen=True, slots=True)
class Viewer:
    name: str
    email: str
    initials: str
    needs_affiliation_declaration: bool


@dataclass(frozen=True, slots=True)
class Shell:
    title: str
    active_page: str
    viewer: Viewer | None
    environment: str
    version: str
    commit: str


@dataclass(frozen=True, slots=True)
class UploadPolicy:
    max_files: int
    max_size_mb: int


@dataclass(frozen=True, slots=True)
class UploadForm:
    policy: UploadPolicy
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DashboardEntry:
    request_id: str
    file_name: str
    created: datetime
    status: str
    progress: int | None
    header_status: CheckStatus
    header_errors: bool
    signatures_status: CheckStatus
    syntax_status: CheckStatus
    schema_status: CheckStatus
    normative_status: CheckStatus
    industry_status: CheckStatus
    pdf_ready: bool = False
    pdf_pending: bool = False
    can_delete: bool = False
    selected: bool = False


@dataclass(frozen=True, slots=True)
class DashboardOptions:
    page: int = 1
    per_page: int = 5
    selected: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Dashboard:
    entries: tuple[DashboardEntry, ...]
    options: DashboardOptions
    total: int
    first: int
    last: int
    previous_page: int | None
    next_page: int | None
    poll: bool
    selected: tuple[str, ...]
    off_page_selected: tuple[str, ...]
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AllowlistPattern:
    field: str
    operation: str
    value: str


@dataclass(frozen=True, slots=True)
class AllowlistEntry:
    id: int
    description: str
    patterns: tuple[AllowlistPattern, ...]


@dataclass(frozen=True, slots=True)
class Allowlist:
    entries: tuple[AllowlistEntry, ...]


@dataclass(frozen=True, slots=True)
class ValidationLayer:
    title: str
    description: str


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    number: str
    title: str
    description: str


@dataclass(frozen=True, slots=True)
class FAQ:
    question: str
    answer: str


@dataclass(frozen=True, slots=True)
class Resource:
    category: str
    title: str
    description: str
    url: str


@dataclass(frozen=True, slots=True)
class LandingPage:
    layers: tuple[ValidationLayer, ...]
    steps: tuple[WorkflowStep, ...]
    faqs: tuple[FAQ, ...]
    resources: tuple[Resource, ...]
