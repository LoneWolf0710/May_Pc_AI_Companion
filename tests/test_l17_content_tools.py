"""Unit tests for core.layers.L17_content_tools — content & utility tools.

Covers: calculate, unit_convert, hash_string, base64_encode, base64_decode,
         json_format, csv_to_json

Run: python -m pytest tests/test_l17_content_tools.py -v
  or: python tests/test_l17_content_tools.py
"""

import asyncio
import csv
import hashlib
import json
import os
import sys
import io
import tempfile

# Fix Windows console encoding for Unicode output when run standalone.
# NOTE: Gated to __main__ so pytest's capture manager is not broken (wrapping
# sys.stdout/stderr at import time caused "I/O operation on closed file" /
# "lost sys.stderr" crashes that aborted the whole test session).
if __name__ == "__main__" and sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.layers.L17_content_tools import (
    _calculate,
    _unit_convert,
    _hash_string,
    _base64_encode,
    _base64_decode,
    _json_format,
    _csv_to_json,
)

passed = 0
failed = 0


def check(condition, label):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {label}")
    else:
        failed += 1
        print(f"  ❌ {label}")
    assert condition, f"FAILED: {label}"


def run(coro):
    """Run an async function in a new event loop."""
    return asyncio.run(coro)


# ══════════════════════════════════════════════════════════════════════════════
# 1. calculate
# ══════════════════════════════════════════════════════════════════════════════

def test_calculate_basic_arithmetic():
    print("\n[1] calculate — basic arithmetic")
    r = run(_calculate({"expression": "2 + 2"}))
    check(r["result"] == 4, "2 + 2 = 4")

    r = run(_calculate({"expression": "10 * 5"}))
    check(r["result"] == 50, "10 * 5 = 50")

    r = run(_calculate({"expression": "100 / 4"}))
    check(r["result"] == 25.0, "100 / 4 = 25.0")

    r = run(_calculate({"expression": "2 ** 10"}))
    check(r["result"] == 1024, "2 ** 10 = 1024")

    r = run(_calculate({"expression": "17 % 5"}))
    check(r["result"] == 2, "17 % 5 = 2")


def test_calculate_percent_of():
    print("\n[2] calculate — percentage of")
    r = run(_calculate({"expression": "15% of 200"}))
    check(r["result"] == 30.0, "15% of 200 = 30")

    r = run(_calculate({"expression": "50% of 100"}))
    check(r["result"] == 50.0, "50% of 100 = 50")

    r = run(_calculate({"expression": "0.5% of 1000"}))
    check(r["result"] == 5.0, "0.5% of 1000 = 5")


def test_calculate_math_functions():
    print("\n[3] calculate — math functions")
    r = run(_calculate({"expression": "sqrt(144)"}))
    check(r["result"] == 12.0, "sqrt(144) = 12")

    r = run(_calculate({"expression": "abs(-42)"}))
    check(r["result"] == 42, "abs(-42) = 42")

    r = run(_calculate({"expression": "min(3, 7, 1)"}))
    check(r["result"] == 1, "min(3,7,1) = 1")

    r = run(_calculate({"expression": "max(3, 7, 1)"}))
    check(r["result"] == 7, "max(3,7,1) = 7")

    r = run(_calculate({"expression": "round(3.14159, 2)"}))
    check(r["result"] == 3.14, "round(pi, 2) = 3.14")


def test_calculate_with_pi_e():
    print("\n[4] calculate — pi and e constants")
    import math
    r = run(_calculate({"expression": "pi"}))
    check(abs(r["result"] - math.pi) < 1e-10, "pi ≈ 3.14159...")

    r = run(_calculate({"expression": "e"}))
    check(abs(r["result"] - math.e) < 1e-10, "e ≈ 2.71828...")


def test_calculate_caret_operator():
    print("\n[5] calculate — caret (^) as power")
    r = run(_calculate({"expression": "2^8"}))
    check(r["result"] == 256, "2^8 = 256")


def test_calculate_error_cases():
    print("\n[6] calculate — error cases")
    r = run(_calculate({"expression": ""}))
    check("error" in r, "empty expression → error")

    r = run(_calculate({"expression": "import os"}))
    check("error" in r, "dangerous code → error (sandboxed)")

    r = run(_calculate({"expression": "open('file')"}))
    check("error" in r, "open() call → error (sandboxed)")

    r = run(_calculate({}))
    check("error" in r, "missing expression → error")


def test_calculate_unit_conversion_shorthand():
    print("\n[7] calculate — inline unit conversion")
    r = run(_calculate({"expression": "100 celsius to fahrenheit"}))
    check("error" not in r, "100 celsius to fahrenheit → success")
    if "error" not in r:
        check(r.get("result") == 212.0 or abs(r.get("result", 0) - 212) < 1, "100C ≈ 212F")


# ══════════════════════════════════════════════════════════════════════════════
# 2. unit_convert
# ══════════════════════════════════════════════════════════════════════════════

def test_unit_convert_length():
    print("\n[8] unit_convert — length")
    r = run(_unit_convert({"value": 1, "from_unit": "km", "to_unit": "mi"}))
    check("error" not in r, "1 km → mi")
    if "error" not in r:
        check(0.621 < r["result"] < 0.622, f"1 km ≈ 0.621 mi (got {r['result']})")

    r = run(_unit_convert({"value": 12, "from_unit": "in", "to_unit": "cm"}))
    check("error" not in r, "12 in → cm")
    if "error" not in r:
        check(abs(r["result"] - 30.48) < 0.01, f"12 in ≈ 30.48 cm (got {r['result']})")


def test_unit_convert_weight():
    print("\n[9] unit_convert — weight")
    r = run(_unit_convert({"value": 1, "from_unit": "kg", "to_unit": "lb"}))
    check("error" not in r, "1 kg → lb")
    if "error" not in r:
        check(2.20 < r["result"] < 2.21, f"1 kg ≈ 2.205 lb (got {r['result']})")


def test_unit_convert_temperature():
    print("\n[10] unit_convert — temperature")
    r = run(_unit_convert({"value": 100, "from_unit": "c", "to_unit": "f"}))
    check("error" not in r, "100C → F")
    if "error" not in r:
        check(r["result"] == 212.0, f"100C = 212F (got {r['result']})")

    r = run(_unit_convert({"value": 0, "from_unit": "f", "to_unit": "c"}))
    check("error" not in r, "0F → C")
    if "error" not in r:
        check(r["result"] == -17.7778, f"0F = -17.7778C (got {r['result']})")

    r = run(_unit_convert({"value": 273.15, "from_unit": "k", "to_unit": "c"}))
    check("error" not in r, "273.15K → C")
    if "error" not in r:
        check(abs(r["result"]) < 0.01, f"273.15K ≈ 0C (got {r['result']})")


def test_unit_convert_data():
    print("\n[11] unit_convert — data")
    r = run(_unit_convert({"value": 1, "from_unit": "gb", "to_unit": "mb"}))
    check("error" not in r, "1 GB → MB")
    if "error" not in r:
        check(r["result"] == 1024, f"1 GB = 1024 MB (got {r['result']})")


def test_unit_convert_time():
    print("\n[12] unit_convert — time")
    r = run(_unit_convert({"value": 2, "from_unit": "h", "to_unit": "min"}))
    check("error" not in r, "2 h → min")
    if "error" not in r:
        check(r["result"] == 120.0, f"2 h = 120 min (got {r['result']})")


def test_unit_convert_errors():
    print("\n[13] unit_convert — error cases")
    r = run(_unit_convert({"value": 1, "from_unit": "", "to_unit": "kg"}))
    check("error" in r, "missing from_unit → error")

    r = run(_unit_convert({"value": 1, "from_unit": "kg", "to_unit": ""}))
    check("error" in r, "missing to_unit → error")

    r = run(_unit_convert({"value": "abc", "from_unit": "kg", "to_unit": "lb"}))
    check("error" in r, "invalid value → error")

    r = run(_unit_convert({"value": 1, "from_unit": "lightyear", "to_unit": "parsec"}))
    check("error" in r, "unknown conversion → error")


def test_unit_convert_reverse_lookup():
    print("\n[14] unit_convert — reverse lookup")
    # (m, ft) exists, but (ft, m) should also work via reverse
    r = run(_unit_convert({"value": 3.28084, "from_unit": "ft", "to_unit": "m"}))
    check("error" not in r, "ft → m reverse lookup")
    if "error" not in r:
        check(abs(r["result"] - 1.0) < 0.001, f"3.28084 ft ≈ 1 m (got {r['result']})")


# ══════════════════════════════════════════════════════════════════════════════
# 3. hash_string
# ══════════════════════════════════════════════════════════════════════════════

def test_hash_string_sha256():
    print("\n[15] hash_string — SHA-256")
    r = run(_hash_string({"text": "hello", "algorithm": "sha256"}))
    check("error" not in r, "sha256 hash")
    if "error" not in r:
        expected = hashlib.sha256("hello".encode()).hexdigest()
        check(r["hash"] == expected, f"sha256('hello') correct")
        check(r["algorithm"] == "sha256", "algorithm reported correctly")


def test_hash_string_md5():
    print("\n[16] hash_string — MD5")
    r = run(_hash_string({"text": "test", "algorithm": "md5"}))
    check("error" not in r, "md5 hash")
    if "error" not in r:
        expected = hashlib.md5("test".encode()).hexdigest()
        check(r["hash"] == expected, f"md5('test') correct")


def test_hash_string_sha1():
    print("\n[17] hash_string — SHA-1")
    r = run(_hash_string({"text": "abc", "algorithm": "sha1"}))
    check("error" not in r, "sha1 hash")
    if "error" not in r:
        expected = hashlib.sha1("abc".encode()).hexdigest()
        check(r["hash"] == expected, f"sha1('abc') correct")


def test_hash_string_default_is_sha256():
    print("\n[18] hash_string — default algorithm")
    r = run(_hash_string({"text": "hello"}))
    check("error" not in r, "default algo works")
    if "error" not in r:
        expected = hashlib.sha256("hello".encode()).hexdigest()
        check(r["hash"] == expected, "default = sha256")


def test_hash_string_errors():
    print("\n[19] hash_string — error cases")
    r = run(_hash_string({"text": ""}))
    check("error" in r, "empty text → error")

    r = run(_hash_string({"text": "test", "algorithm": "md6"}))
    check("error" in r, "unknown algorithm → error")

    r = run(_hash_string({}))
    check("error" in r, "missing text → error")


def test_hash_string_utf8():
    print("\n[20] hash_string — UTF-8 support")
    r = run(_hash_string({"text": "日本語テスト"}))
    check("error" not in r, "UTF-8 text hashes without error")
    if "error" not in r:
        expected = hashlib.sha256("日本語テスト".encode("utf-8")).hexdigest()
        check(r["hash"] == expected, "UTF-8 hash matches expected")


# ══════════════════════════════════════════════════════════════════════════════
# 4. base64_encode / base64_decode
# ══════════════════════════════════════════════════════════════════════════════

def test_base64_encode_basic():
    print("\n[21] base64_encode — basic")
    import base64
    r = run(_base64_encode({"text": "hello"}))
    check("error" not in r, "encode 'hello'")
    if "error" not in r:
        check(r["encoded"] == "aGVsbG8=", f"base64('hello') = aGVsbG8= (got {r['encoded']})")

    r = run(_base64_encode({"text": "Hello, World!"}))
    check("error" not in r, "encode 'Hello, World!'")
    if "error" not in r:
        expected = base64.b64encode("Hello, World!".encode()).decode()
        check(r["encoded"] == expected, "matches manual base64")


def test_base64_decode_basic():
    print("\n[22] base64_decode — basic")
    r = run(_base64_decode({"encoded": "aGVsbG8="}))
    check("error" not in r, "decode aGVsbG8=")
    if "error" not in r:
        check(r["decoded"] == "hello", f"decoded = 'hello' (got {r['decoded']!r})")


def test_base64_roundtrip():
    print("\n[23] base64 — encode → decode roundtrip")
    test_strings = ["hello", "Hello, World!", "1234567890", "special chars: !@#$%^&*()", ""]
    for s in test_strings:
        enc = run(_base64_encode({"text": s}))
        if s == "":
            check("error" in enc, f"empty string → error on encode")
            continue
        dec = run(_base64_decode({"encoded": enc["encoded"]}))
        check(dec.get("decoded") == s, f"roundtrip '{s}' OK")


def test_base64_encode_empty():
    print("\n[24] base64_encode — error cases")
    r = run(_base64_encode({"text": ""}))
    check("error" in r, "empty text → error")

    r = run(_base64_encode({}))
    check("error" in r, "missing text → error")


def test_base64_decode_errors():
    print("\n[25] base64_decode — error cases")
    r = run(_base64_decode({"encoded": ""}))
    check("error" in r, "empty encoded → error")

    r = run(_base64_decode({"encoded": "!!!not-valid-base64!!!"}))
    check("error" in r, "invalid base64 → error")

    r = run(_base64_decode({}))
    check("error" in r, "missing encoded → error")


def test_base64_utf8():
    print("\n[26] base64 — UTF-8 support")
    enc = run(_base64_encode({"text": "日本語"}))
    check("error" not in enc, "encode UTF-8")
    dec = run(_base64_decode({"encoded": enc["encoded"]}))
    check(dec.get("decoded") == "日本語", "roundtrip UTF-8 '日本語'")


# ══════════════════════════════════════════════════════════════════════════════
# 5. json_format
# ══════════════════════════════════════════════════════════════════════════════

def test_json_format_pretty():
    print("\n[27] json_format — pretty-print")
    r = run(_json_format({"json_string": '{"name":"May","age":3,"active":true}'}))
    check("error" not in r, "parse valid JSON")
    if "error" not in r:
        check(r["keys"] == 3, f"key count = 3 (got {r['keys']})")
        # Pretty-printed should have newlines
        check("\n" in r["formatted"], "formatted has newlines")
        # Should be valid JSON roundtrip
        parsed_back = json.loads(r["formatted"])
        check(parsed_back["name"] == "May", "name = May")
        check(parsed_back["age"] == 3, "age = 3")


def test_json_format_different_indent():
    print("\n[28] json_format — custom indent")
    r = run(_json_format({"json_string": '{"a":1}', "indent": 4}))
    check("error" not in r, "indent=4")
    if "error" not in r:
        check("    " in r["formatted"], "4-space indent present")


def test_json_format_list():
    print("\n[29] json_format — array input")
    r = run(_json_format({"json_string": "[1,2,3]"}))
    check("error" not in r, "array parsed")
    if "error" not in r:
        check(r["keys"] is None, "keys=None for array")


def test_json_format_invalid():
    print("\n[30] json_format — invalid JSON")
    r = run(_json_format({"json_string": "{not valid json}"}))
    check("error" in r, "invalid JSON → error")

    r = run(_json_format({"json_string": ""}))
    check("error" in r, "empty string → error")

    r = run(_json_format({}))
    check("error" in r, "missing json_string → error")


def test_json_format_unicode():
    print("\n[31] json_format — unicode handling")
    r = run(_json_format({"json_string": '{"emoji":"🌸","japanese":"日本語"}'}))
    check("error" not in r, "unicode JSON parsed")
    if "error" not in r:
        check("🌸" in r["formatted"], "emoji preserved")
        check("日本語" in r["formatted"], "japanese preserved")


# ══════════════════════════════════════════════════════════════════════════════
# 6. csv_to_json
# ══════════════════════════════════════════════════════════════════════════════

def _write_csv(rows, columns):
    """Helper: write CSV to a temp file and return path."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_csv_to_json_basic():
    print("\n[32] csv_to_json — basic")
    path = _write_csv(
        [{"name": "May", "age": "3"}, {"name": "Shikimori", "age": "18"}],
        ["name", "age"],
    )
    try:
        r = run(_csv_to_json({"csv_path": path}))
        check("error" not in r, "parse basic CSV")
        if "error" not in r:
            check(r["row_count"] == 2, f"2 rows (got {r['row_count']})")
            check("name" in r["columns"], "columns include 'name'")
            check(r["json"][0]["name"] == "May", "first row name = May")
    finally:
        os.unlink(path)


def test_csv_to_json_single_column():
    print("\n[33] csv_to_json — single column")
    path = _write_csv([{"item": "apple"}, {"item": "banana"}], ["item"])
    try:
        r = run(_csv_to_json({"csv_path": path}))
        check("error" not in r, "single column CSV")
        if "error" not in r:
            check(r["row_count"] == 2, "2 rows")
            check(r["columns"] == ["item"], "one column")
    finally:
        os.unlink(path)


def test_csv_to_json_empty_file():
    print("\n[34] csv_to_json — empty CSV")
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        r = run(_csv_to_json({"csv_path": path}))
        # Empty CSV with no header → empty list
        check("error" not in r or r.get("row_count", 0) == 0, "empty CSV handled")
    finally:
        os.unlink(path)


def test_csv_to_json_missing_file():
    print("\n[35] csv_to_json — missing file")
    r = run(_csv_to_json({"csv_path": "/nonexistent/path.csv"}))
    check("error" in r, "missing file → error")


def test_csv_to_json_errors():
    print("\n[36] csv_to_json — error cases")
    r = run(_csv_to_json({"csv_path": ""}))
    check("error" in r, "empty path → error")

    r = run(_csv_to_json({}))
    check("error" in r, "missing csv_path → error")


def test_csv_to_json_special_characters():
    print("\n[37] csv_to_json — special characters")
    path = _write_csv(
        [{"name": "O'Brien", "note": 'He said "hello"'}],
        ["name", "note"],
    )
    try:
        r = run(_csv_to_json({"csv_path": path}))
        check("error" not in r, "special chars parsed")
        if "error" not in r:
            check(r["json"][0]["name"] == "O'Brien", "apostrophe preserved")
            check("hello" in r["json"][0]["note"], "quotes in value")
    finally:
        os.unlink(path)


def test_csv_to_json_numeric_values():
    print("\n[38] csv_to_json — numeric values (read as strings)")
    path = _write_csv(
        [{"x": "1.5", "y": "2.5"}],
        ["x", "y"],
    )
    try:
        r = run(_csv_to_json({"csv_path": path}))
        check("error" not in r, "numeric CSV parsed")
        if "error" not in r:
            # CSV values are always strings
            check(r["json"][0]["x"] == "1.5", "value = '1.5' (string)")
    finally:
        os.unlink(path)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_calculate_basic_arithmetic()
    test_calculate_percent_of()
    test_calculate_math_functions()
    test_calculate_with_pi_e()
    test_calculate_caret_operator()
    test_calculate_error_cases()
    test_calculate_unit_conversion_shorthand()
    test_unit_convert_length()
    test_unit_convert_weight()
    test_unit_convert_temperature()
    test_unit_convert_data()
    test_unit_convert_time()
    test_unit_convert_errors()
    test_unit_convert_reverse_lookup()
    test_hash_string_sha256()
    test_hash_string_md5()
    test_hash_string_sha1()
    test_hash_string_default_is_sha256()
    test_hash_string_errors()
    test_hash_string_utf8()
    test_base64_encode_basic()
    test_base64_decode_basic()
    test_base64_roundtrip()
    test_base64_encode_empty()
    test_base64_decode_errors()
    test_base64_utf8()
    test_json_format_pretty()
    test_json_format_different_indent()
    test_json_format_list()
    test_json_format_invalid()
    test_json_format_unicode()
    test_csv_to_json_basic()
    test_csv_to_json_single_column()
    test_csv_to_json_empty_file()
    test_csv_to_json_missing_file()
    test_csv_to_json_errors()
    test_csv_to_json_special_characters()
    test_csv_to_json_numeric_values()

    total = passed + failed
    print(f"\n{'='*60}")
    print(f"  Results: ✅ {passed} passed, ❌ {failed} failed / {total} total")
    print(f"{'='*60}\n")
    sys.exit(0 if failed == 0 else 1)
