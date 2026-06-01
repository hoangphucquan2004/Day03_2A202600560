from typing import Any, Dict, List, Optional

from src.agent.agent import ReActAgent
from src.core.llm_provider import LLMProvider
from src.tools.course_registration_tools import get_course_registration_tools


class ScriptedLLM(LLMProvider):
    def __init__(self, responses: List[str]):
        super().__init__(model_name="scripted-test-llm")
        self.responses = responses
        self.calls = 0

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        response = self.responses[self.calls]
        self.calls += 1
        return {
            "content": response,
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "total_tokens": 20,
            },
            "latency_ms": 1,
            "provider": "scripted",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None):
        yield self.generate(prompt, system_prompt)["content"]


def test_react_agent_calls_two_tools_and_returns_final_answer():
    llm = ScriptedLLM(
        [
            'Thought: I need to check seats first.\n'
            'Action: check_slots({"course_query": ["AI", "Data Science"]})',
            'Thought: Both courses have available options, so I need tuition.\n'
            'Action: get_tuition({"course_code": ["AI3010", "DATA3020"], "student_id": "2A202600713"})',
            "Thought: I have the slot and tuition observations.\n"
            "Final Answer: AI and Data Science both have available sections. "
            "The estimated total tuition and fees are 19,150,000 VND.",
        ]
    )
    agent = ReActAgent(llm=llm, tools=get_course_registration_tools(), max_steps=5)

    answer = agent.run("Tôi muốn đăng ký môn AI và Data Science, kiểm tra còn chỗ không và học phí tổng cộng?")

    assert "19,150,000 VND" in answer
    assert llm.calls == 3


def test_react_agent_runs_full_registration_flow():
    llm = ScriptedLLM(
        [
            'Thought: I need to check seats first.\n'
            'Action: check_slots({"course_query": ["AI", "Data Science"]})',
            'Thought: Seats are available, so I need tuition.\n'
            'Action: get_tuition({"course_code": ["AI3010", "DATA3020"], "student_id": "2A202600713"})',
            'Thought: Tuition is available, so I can register the selected sections.\n'
            'Action: register({"student_id": "2A202600713", "section_ids": ["AI3010-01", "DATA3020-02"], "confirm_payment": true})',
            "Thought: Registration succeeded.\n"
            "Final Answer: AI3010-01 and DATA3020-02 were registered successfully. "
            "The estimated total is 19,150,000 VND.",
        ]
    )
    agent = ReActAgent(llm=llm, tools=get_course_registration_tools(), max_steps=6)

    answer = agent.run("Register AI and Data Science for student 2A202600713.")

    assert "registered successfully" in answer
    assert llm.calls == 4


def test_react_agent_handles_unknown_tool_as_failure_trace():
    llm = ScriptedLLM(
        [
            'Thought: I will call a tool that does not exist.\n'
            'Action: search_course({"query": "AI"})',
            "Thought: The observation says the tool does not exist.\n"
            "Final Answer: I cannot use that tool, so I should call check_slots instead.",
        ]
    )
    agent = ReActAgent(llm=llm, tools=get_course_registration_tools(), max_steps=3)

    answer = agent.run("Check AI slots")

    assert "check_slots" in answer
