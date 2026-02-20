"""
Initial tests moving away from Django towards FastAPI/Pydantic    
"""
import pytest
from pydantic import ValidationError, TypeAdapter
from django.core.files.uploadedfile import SimpleUploadedFile # to be deleted after making schema DjangoDRF/FastAPI agnostic

from apps.ifc_validation.api.v1.schemas import ValidationRequestIn
from core.settings import MAX_FILE_SIZE_IN_MB

TA = TypeAdapter(ValidationRequestIn)

def make_uploaded(name: str, size: int) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name=name,
        content=b"\x00" * size,
        content_type="application/octet-stream",
    )

def test_valid_file_passes():
    f = make_uploaded("ok.ifc", 100)
    m = TA.validate_python({"file": f, "file_name": "ok.ifc", "size": 100})
    assert m.file_name == "ok.ifc"
    assert m.file.size == 100

def test_missing_file_raises():
    with pytest.raises(ValidationError) as e:
        TA.validate_python({"file": None, "file_name": "ok.ifc", "size": 1})
    assert "File is required." in str(e.value)

def test_bad_extension_raises():
    f = make_uploaded("bad.txt", 100)
    with pytest.raises(ValidationError) as e:
        TA.validate_python({"file": f, "file_name": "bad.txt", "size": 100})
    assert "File name must end with '.ifc'." in str(e.value)

def test_negative_size_raises():
    f = make_uploaded("ok.ifc", 100)
    with pytest.raises(ValidationError) as e:
        TA.validate_python({"file": f, "file_name": "ok.ifc", "size": -5})
    assert "Size must be positive." in str(e.value)

def test_too_large_file_raises():
    too_big = (MAX_FILE_SIZE_IN_MB + 1) * 1024 * 1024
    f = make_uploaded("ok.ifc", too_big)
    with pytest.raises(ValidationError) as e:
        TA.validate_python({"file": f, "file_name": "ok.ifc", "size": too_big})
    assert f"File size exceeds allowed file size limit ({MAX_FILE_SIZE_IN_MB} MB)." in str(e.value)
