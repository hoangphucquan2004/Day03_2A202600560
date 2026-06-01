from src.tools.course_registration_tools import check_slots, get_tuition


def test_check_slots_supports_multiple_course_names():
    result = check_slots("AI và Data Science")

    assert result["ok"] is True
    assert [course["course_code"] for course in result["courses"]] == ["AI3010", "DATA3020"]
    assert all(course["availability_status"] == "available" for course in result["courses"])


def test_get_tuition_calculates_total_for_multiple_courses():
    result = get_tuition(["AI3010", "DATA3020"], student_id="2A202600713")

    assert result["ok"] is True
    assert result["currency"] == "VND"
    assert result["tuition_category"] == "domestic"
    assert result["estimated_total"] == 19150000


def test_get_tuition_returns_error_for_unknown_student():
    result = get_tuition("AI3010", student_id="UNKNOWN")

    assert result["ok"] is False
    assert result["errors"] == ["Student not found."]
