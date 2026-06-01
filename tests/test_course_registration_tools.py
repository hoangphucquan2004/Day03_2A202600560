from src.tools.course_registration_tools import check_slots, get_course_registration_tools, get_tuition, register


def test_check_slots_supports_multiple_course_names():
    result = check_slots("AI và Data Science")

    assert result["ok"] is True
    assert [course["course_code"] for course in result["courses"]] == ["AI3010", "DATA3020"]
    assert all(course["availability_status"] == "available" for course in result["courses"])


def test_check_slots_supports_natural_language_query():
    result = check_slots("Tôi muốn đăng ký môn AI và Data Science, kiểm tra còn chỗ không?")

    assert result["ok"] is True
    assert [course["course_code"] for course in result["courses"]] == ["AI3010", "DATA3020"]


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


def test_full_course_registration_flow():
    slots = check_slots("AI và Data Science")
    course_codes = [course["course_code"] for course in slots["courses"]]
    tuition = get_tuition(course_codes, student_id="2A202600713")
    registration = register(
        student_id="2A202600713",
        section_ids=["AI3010-01", "DATA3020-02"],
        confirm_payment=True,
    )

    assert slots["ok"] is True
    assert tuition["ok"] is True
    assert tuition["estimated_total"] == 19150000
    assert registration["ok"] is True
    assert registration["registration_status"] == "registered"


def test_tool_registry_includes_register():
    tool_names = [tool["name"] for tool in get_course_registration_tools()]

    assert "check_slots" in tool_names
    assert "get_tuition" in tool_names
    assert "register" in tool_names
