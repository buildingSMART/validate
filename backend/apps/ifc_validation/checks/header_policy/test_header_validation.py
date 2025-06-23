import pytest
import ifcopenshell
from pathlib import Path
from validate_header import HeaderStructure
import sys

def collect_test_files():
    test_dir = Path(__file__).parent / "tests"
    return [
        (str(file), outcome, field_folder.name)
        for field_folder in test_dir.iterdir() if field_folder.is_dir()
        for outcome in ["pass", "fail"]
        for file in (field_folder / outcome).glob("*.ifc")
    ]

@pytest.mark.parametrize("f", collect_test_files())
def test_invocation(f):
    filename, outcome, field = f[0], f[1], f[2]
    file = ifcopenshell.simple_spf.open(filename, only_header=True)
    header = HeaderStructure(file=file)
    
    assert (field not in header.validation_errors) if outcome == 'pass' else (field in header.validation_errors)


def run_single_file(filename=''):
    if filename:
        file = ifcopenshell.simple_spf.open(filename, only_header=True)
        print(header.validation_errors)
        header = HeaderStructure(file=file)

if __name__ == "__main__":
    if len(sys.argv) == 2:
        single_file = sys.argv[1]
        run_single_file(single_file)
    else:
        pytest.main(["-sv", __file__])