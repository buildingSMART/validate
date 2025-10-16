from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, field_validator
from django.core.files.uploadedfile import UploadedFile
from core.settings import MAX_FILE_SIZE_IN_MB

class _Base(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

class ValidationRequestIn(_Base):
    file: Optional[UploadedFile] = None
    files: Optional[List[UploadedFile]] = None
    file_name: Optional[str] = None
    size: Optional[int] = None

    @field_validator("file")
    @classmethod
    def file_required_and_under_limit(cls, v: Optional[UploadedFile]):
        if v is None:
            raise ValueError("File is required.")
        max_bytes = MAX_FILE_SIZE_IN_MB * 1024 * 1024
        if v.size > max_bytes:
            raise ValueError(f"File size exceeds allowed file size limit ({MAX_FILE_SIZE_IN_MB} MB).")
        return v

    @field_validator("files")
    @classmethod
    def at_most_one_file(cls, v: Optional[List[UploadedFile]]):
        if v is None:
            return v
        if len(v) != 1:
            raise ValueError("Only one file can be uploaded at a time.")
        return v

    @field_validator("file_name")
    @classmethod
    def file_name_ifc(cls, v: Optional[str]):
        if not v:
            raise ValueError("File name is required.")
        if not v.lower().endswith(".ifc"):
            raise ValueError("File name must end with '.ifc'.")
        return v

    @field_validator("size")
    @classmethod
    def size_positive_and_under_limit(cls, v: Optional[int]):
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Size must be positive.")
        max_bytes = MAX_FILE_SIZE_IN_MB * 1024 * 1024
        if v > max_bytes:
            raise ValueError(f"File size exceeds allowed file size limit ({MAX_FILE_SIZE_IN_MB} MB).")
        return v


class ValidationTaskIn(_Base):
    request_public_id: Optional[str] = None


class ValidationOutcomeIn(_Base):
    instance_public_id: Optional[str] = None
    validation_task_public_id: Optional[str] = None


class ModelIn(_Base):
    public_id: Optional[str] = None