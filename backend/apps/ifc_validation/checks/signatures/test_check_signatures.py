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


def test_strip_content_matches_per_character_filter():
    def reference(data):
        return "".join(char for char in data if 0x20 <= ord(char) <= 0xFF and ord(char) != 0x7F)

    # controls, printable ASCII, DEL, latin-1 range and codepoints beyond 0xFF
    sample = "".join(map(chr, range(0x300))) + "DATA;\r\n\t/* SIGNATURE; abc ENDSEC; */\x00"
    assert check_signatures.strip_content(sample) == reference(sample)


@pytest.mark.parametrize(
    "content,expected,chunk_size",
    [
        (b"ISO-10303-21;\nDATA;\nENDSEC;\n", False, 1024),
        (b"DATA;\n/* SIGNATURE;\nabc\nENDSEC; */", True, 1024),
        # marker interrupted by a line ending, stripped away before matching
        (b"DATA;\n/* SIGNA\r\nTURE;\nabc ENDSEC; */", True, 1024),
        # marker straddling a chunk boundary
        (b"x" * 10 + b"/* SIGNATURE; y ENDSEC; */", True, 16),
        (b"\x80\x81ISO-10303-21;", False, 1024),
        (b"", False, 1024),
    ],
)
def test_contains_signature(tmp_path, content, expected, chunk_size):
    fn = tmp_path / "input.ifc"
    fn.write_bytes(content)
    assert check_signatures.contains_signature(fn, chunk_size=chunk_size) == expected


if __name__ == "__main__":
    if len(sys.argv) == 2:
        check_signatures.run(sys.argv[1])
    else:
        pytest.main(["-sv", __file__])
