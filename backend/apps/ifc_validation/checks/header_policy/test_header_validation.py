import pytest
import ifcopenshell
from pathlib import Path
from validate_header import HeaderStructure

def collect_test_files():
    return [
        (str(file), outcome, field_folder.name)
        for field_folder in Path("tests").iterdir() if field_folder.is_dir()
        for outcome in ["pass", "fail"]
        for file in field_folder.glob(f"{outcome}_*.ifc")
    ]

@pytest.mark.parametrize("f", collect_test_files())
def test_invocation(f):
    filename, outcome, field = f[0], f[1], f[2]
    file = ifcopenshell.open(filename)
    try:
        header = HeaderStructure(file=file)
    except:
        pass
    assert (field not in header.validation_errors) if outcome == 'pass' else (field in header.validation_errors)


if __name__ == "__main__":
    pytest.main(["-s", __file__])