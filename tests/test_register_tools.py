"""
Tests for register_tools module.
"""
from src.tools.register_tools import get_register_tool, register


def test_register_success_for_main_flow_sections():
    result = register(
        student_id="2A202600713",
        section_ids=["AI3010-01", "DATA3020-02"],
        confirm_payment=True,
    )

    assert result["ok"] is True
    assert result["registration_status"] == "registered"
    assert [section["section_id"] for section in result["registered_sections"]] == ["AI3010-01", "DATA3020-02"]
    assert result["waitlisted_sections"] == []


def test_register_waitlists_when_open_seat_is_unavailable():
    result = register(
        student_id="2A202600713",
        section_ids=["AI3010-02"],
        confirm_payment=True,
    )

    assert result["ok"] is True
    assert result["registration_status"] == "waitlisted"
    assert result["registered_sections"] == []
    assert result["waitlisted_sections"][0]["section_id"] == "AI3010-02"


def test_register_blocks_financial_hold():
    result = register(
        student_id="2A202600999",
        section_ids=["AI3010-01"],
        confirm_payment=True,
    )

    assert result["ok"] is False
    assert result["registration_status"] == "failed"
    assert any("FINANCE_BALANCE" in error for error in result["errors"])


def test_register_requires_payment_confirmation():
    result = register(
        student_id="2A202600713",
        section_ids=["AI3010-01"],
        confirm_payment=False,
    )

    assert result["ok"] is False
    assert "Payment confirmation is required before final registration." in result["errors"]


def test_get_register_tool_definition():
    tool = get_register_tool()

    assert tool["name"] == "register"
    assert "description" in tool
    assert "function" in tool
    assert callable(tool["function"])
