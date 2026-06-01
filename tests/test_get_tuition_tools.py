"""
Tests for get_tuition_tools module.
"""
from src.tools.get_tuition_tools import get_tuition, get_get_tuition_tool


def test_get_tuition_single_course():
    """Test get_tuition with a single course."""
    result = get_tuition("AI3010", student_id="2A202600713")

    assert result["ok"] is True
    assert result["student_id"] == "2A202600713"
    assert result["student_name"] == "Hai Dang Minh"
    assert result["tuition_category"] == "domestic"
    assert result["currency"] == "VND"
    assert len(result["courses"]) == 1
    assert result["courses"][0]["course_code"] == "AI3010"
    assert result["estimated_total"] > 0


def test_get_tuition_multiple_courses():
    """Test get_tuition with multiple courses."""
    result = get_tuition(["AI3010", "DATA3020"], student_id="2A202600713")

    assert result["ok"] is True
    assert len(result["courses"]) == 2
    assert [course["course_code"] for course in result["courses"]] == ["AI3010", "DATA3020"]
    assert result["estimated_total"] == 19150000


def test_get_tuition_domestic_student():
    """Test get_tuition calculates correct domestic student tuition."""
    result = get_tuition("AI3010", student_id="2A202600713")

    assert result["ok"] is True
    assert result["tuition_category"] == "domestic"
    assert result["courses"][0]["per_credit"] == 2800000
    assert result["courses"][0]["base_tuition"] == 8400000
    assert result["courses"][0]["estimated_total"] == 9100000


def test_get_tuition_international_student():
    """Test get_tuition calculates correct international student tuition."""
    result = get_tuition("AI3010", student_id="2A202601102")

    assert result["ok"] is True
    assert result["student_name"] == "Alex Park"
    assert result["tuition_category"] == "international"
    assert result["courses"][0]["per_credit"] == 4200000
    assert result["courses"][0]["base_tuition"] == 12600000
    assert result["courses"][0]["estimated_total"] == 13300000


def test_get_tuition_international_more_expensive():
    """Test that international tuition is more expensive than domestic."""
    domestic = get_tuition("AI3010", student_id="2A202600713")
    international = get_tuition("AI3010", student_id="2A202601102")

    assert domestic["estimated_total"] == 9100000
    assert international["estimated_total"] == 13300000
    assert international["estimated_total"] > domestic["estimated_total"]


def test_get_tuition_includes_fees():
    """Test that get_tuition includes lab and material fees."""
    result = get_tuition("AI3010", student_id="2A202600713")

    course = result["courses"][0]
    assert "fees" in course
    assert "lab_fee" in course["fees"]
    assert "material_fee" in course["fees"]
    assert course["fees"]["lab_fee"] == 500000
    assert course["fees"]["material_fee"] == 200000


def test_get_tuition_invalid_student():
    """Test get_tuition with non-existent student."""
    result = get_tuition("AI3010", student_id="INVALID123")

    assert result["ok"] is False
    assert result["student_id"] == "INVALID123"
    assert "Student not found" in result["errors"][0]


def test_get_tuition_invalid_course():
    """Test get_tuition with non-existent course."""
    result = get_tuition("INVALID999", student_id="2A202600713")

    assert result["ok"] is False
    assert len(result["courses"]) == 0
    assert "No matching course found" in result["errors"][0]


def test_get_tuition_partial_match_multiple_courses():
    """Test get_tuition with course name that matches multiple."""
    result = get_tuition("Data Science", student_id="2A202600713")

    assert result["ok"] is True
    assert len(result["courses"]) >= 1


def test_get_tuition_with_course_alias():
    """Test get_tuition recognizes course aliases."""
    result1 = get_tuition("AI3010", student_id="2A202600713")
    result2 = get_tuition("AI", student_id="2A202600713")
    result3 = get_tuition("Artificial Intelligence", student_id="2A202600713")

    assert result1["ok"] is True
    assert result2["ok"] is True
    assert result3["ok"] is True
    assert result1["estimated_total"] == result2["estimated_total"] == result3["estimated_total"]


def test_get_tuition_course_details():
    """Test that get_tuition returns detailed course information."""
    result = get_tuition("AI3010", student_id="2A202600713")

    course = result["courses"][0]
    assert "course_code" in course
    assert "title" in course
    assert "credits" in course
    assert "per_credit" in course
    assert "base_tuition" in course
    assert "estimated_total" in course


def test_get_tuition_correct_total_calculation():
    """Test that total is correctly calculated."""
    result = get_tuition("AI3010", student_id="2A202600713")

    course = result["courses"][0]
    expected_total = course["base_tuition"] + course["fees"]["lab_fee"] + course["fees"]["material_fee"]
    assert course["estimated_total"] == expected_total
    assert result["estimated_total"] == expected_total


def test_get_get_tuition_tool_definition():
    """Test that get_get_tuition_tool returns correct tool definition."""
    tool = get_get_tuition_tool()

    assert tool["name"] == "get_tuition"
    assert "description" in tool
    assert "function" in tool
    assert callable(tool["function"])


def test_get_tuition_multiple_courses_total():
    """Test that total for multiple courses is sum of individual totals."""
    result = get_tuition(["AI3010", "DATA3020"], student_id="2A202600713")

    individual_totals = sum(course["estimated_total"] for course in result["courses"])
    assert result["estimated_total"] == individual_totals
    assert result["estimated_total"] == 19150000


def test_get_tuition_empty_course_list():
    """Test get_tuition with empty course list."""
    result = get_tuition([], student_id="2A202600713")

    assert result["ok"] is False
    assert len(result["courses"]) == 0
