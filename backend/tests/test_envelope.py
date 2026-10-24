from __future__ import annotations

from api.envelope import fail, ok


# ---------------------------------------------------------------------------
# UT-ENV-001..003: ok()
# ---------------------------------------------------------------------------


def test_ok_with_dict():
    """UT-ENV-001: ok({"key": "val"}) → {success: true, data: {...}, error: null}."""
    result = ok({"key": "val"})
    assert result["success"] is True
    assert result["data"] == {"key": "val"}
    assert result["error"] is None


def test_ok_with_list():
    """UT-ENV-002: ok([1,2,3]) → data là list."""
    result = ok([1, 2, 3])
    assert result["success"] is True
    assert result["data"] == [1, 2, 3]
    assert result["error"] is None


def test_ok_with_none():
    """UT-ENV-003: ok(None) → data: null."""
    result = ok(None)
    assert result["success"] is True
    assert result["data"] is None
    assert result["error"] is None


# ---------------------------------------------------------------------------
# UT-ENV-004..005: fail()
# ---------------------------------------------------------------------------


def test_fail_creates_error_envelope():
    """UT-ENV-004: fail("CODE", "msg") → {success: false, data: null, error: {code, message}}."""
    result = fail("SCAN_FAILED", "something broke")
    assert result["success"] is False
    assert result["data"] is None
    assert result["error"]["code"] == "SCAN_FAILED"
    assert result["error"]["message"] == "something broke"


def test_fail_error_code_exact():
    """UT-ENV-005: Kiểm tra error.code đúng giá trị truyền vào."""
    result = fail("CUSTOM_CODE", "msg")
    assert result["error"]["code"] == "CUSTOM_CODE"
