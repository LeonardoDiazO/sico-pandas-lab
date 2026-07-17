import pytest

from app.startup_checks import (
    ReadOnlyViolation,
    decide_guard,
    evaluate_privileges,
    verify_read_only,
)


def test_select_only_is_clean():
    assert evaluate_privileges(["SELECT", "USAGE"]) == []


def test_write_privileges_are_flagged():
    assert evaluate_privileges(["SELECT", "INSERT", "UPDATE"]) == ["INSERT", "UPDATE"]


def test_all_privileges_is_flagged():
    assert evaluate_privileges(["ALL PRIVILEGES"]) == ["ALL PRIVILEGES"]


def test_verify_passes_for_read_only_user():
    verdict, _ = verify_read_only(lambda: ["SELECT"])
    assert verdict == "ok"


def test_verify_aborts_boot_for_writable_user_without_optin():
    with pytest.raises(ReadOnlyViolation):
        verify_read_only(lambda: ["SELECT", "DELETE"], allow_write_user=False)


def test_verify_degrades_but_boots_for_writable_user_with_optin():
    verdict, message = verify_read_only(lambda: ["SELECT", "DELETE"], allow_write_user=True)
    assert verdict == "degraded"
    assert "SESSION TRANSACTION READ ONLY" in message


def test_decide_guard_clean_when_read_only():
    assert decide_guard([], allow_write_user=False)[0] == "ok"


def test_decide_guard_abort_beats_optin_default():
    assert decide_guard(["INSERT"], allow_write_user=False)[0] == "abort"
