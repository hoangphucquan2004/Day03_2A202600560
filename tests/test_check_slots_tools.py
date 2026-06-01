"""
Tests for check_slots_tools module.
"""
from src.tools.check_slots_tools import check_slots, get_check_slots_tool


def test_check_slots_single_course_query():
    """Test check_slots with a single course query."""
    result = check_slots("AI")

    assert result["ok"] is True
    assert len(result["courses"]) > 0
    assert result["courses"][0]["course_code"] == "AI3010"
    assert result["courses"][0]["availability_status"] == "available"


def test_check_slots_multiple_courses():
    """Test check_slots with multiple course codes."""
    result = check_slots(["AI3010", "DATA3020"])

    assert result["ok"] is True
    assert len(result["courses"]) == 2
    assert [course["course_code"] for course in result["courses"]] == ["AI3010", "DATA3020"]
    assert all(course["availability_status"] in ["available", "waitlist_available"] for course in result["courses"])


def test_check_slots_with_list_input():
    """Test check_slots with Vietnamese course query."""
    result = check_slots("AI và Data Science")

    assert result["ok"] is True
    assert len(result["courses"]) == 2
    assert [course["course_code"] for course in result["courses"]] == ["AI3010", "DATA3020"]


def test_check_slots_invalid_course():
    """Test check_slots with non-existent course."""
    result = check_slots("INVALID999")

    assert result["ok"] is False
    assert len(result["courses"]) == 0
    assert "No matching course found" in result["errors"][0]


def test_check_slots_returns_detailed_section_info():
    """Test that check_slots returns detailed section information."""
    result = check_slots("AI3010")

    assert result["ok"] is True
    course = result["courses"][0]
    assert "sections" in course
    assert len(course["sections"]) > 0
    
    section = course["sections"][0]
    assert "section_id" in section
    assert "instructor" in section
    assert "schedule" in section
    assert "available_seats" in section
    assert "availability_status" in section


def test_check_slots_handles_course_aliases():
    """Test that check_slots recognizes course aliases."""
    result1 = check_slots("AI")
    result2 = check_slots("AI3010")
    result3 = check_slots("Artificial Intelligence")

    assert result1["ok"] is True
    assert result2["ok"] is True
    assert result3["ok"] is True
    assert result1["courses"][0]["course_code"] == result2["courses"][0]["course_code"]
    assert result2["courses"][0]["course_code"] == result3["courses"][0]["course_code"]


def test_check_slots_term_parameter():
    """Test check_slots with term parameter."""
    result = check_slots("AI3010", term="Fall 2026")

    assert result["ok"] is True
    assert result["term"] == "Fall 2026"


def test_check_slots_term_mismatch_warning():
    """Test check_slots warns when term doesn't match."""
    result = check_slots("AI3010", term="Spring 2027")

    assert result["ok"] is True
    assert len(result["warnings"]) > 0
    assert "Spring 2027" in result["warnings"][0]


def test_get_check_slots_tool_definition():
    """Test that get_check_slots_tool returns correct tool definition."""
    tool = get_check_slots_tool()

    assert tool["name"] == "check_slots"
    assert "description" in tool
    assert "function" in tool
    assert callable(tool["function"])


def test_check_slots_with_empty_string():
    """Test check_slots with empty string."""
    result = check_slots("")

    assert result["ok"] is False
    assert len(result["courses"]) == 0
