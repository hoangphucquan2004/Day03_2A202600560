"""
Tool registry for the course registration assistant.

Individual tool logic lives in separate modules:
- check_slots_tools.py
- get_tuition_tools.py
- register_tools.py
"""
from typing import Any, Dict, List

from src.tools.check_slots_tools import check_slots, get_check_slots_tool
from src.tools.get_tuition_tools import get_get_tuition_tool, get_tuition
from src.tools.register_tools import get_register_tool, register


def get_course_registration_tools() -> List[Dict[str, Any]]:
    return [
        get_check_slots_tool(),
        get_get_tuition_tool(),
        get_register_tool(),
    ]


__all__ = ["check_slots", "get_tuition", "register", "get_course_registration_tools"]
