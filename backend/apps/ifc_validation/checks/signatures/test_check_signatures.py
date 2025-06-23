import pytest
from pathlib import Path
import check_signatures
import sys


@pytest.mark.parametrize("fn", (Path(__file__).parent / "test_files").glob("*.ifc"))
def test_invocation(fn):
    fragment = fn.name.split("_")[0]
    if fragment == "pass":
        assert [1 for res in check_signatures.run(fn) if res.get("signature", "").startswith("valid_")]
    elif fragment == "fail":
        assert [1 for res in check_signatures.run(fn) if res.get("signature", "") == "invalid"]
    elif fragment == "na":
        assert len(list(check_signatures.run(fn))) == 0
    else:
        assert False


if __name__ == "__main__":
    if len(sys.argv) == 2:
        check_signatures.run(sys.argv[1])
    else:
        pytest.main(["-sv", __file__])
