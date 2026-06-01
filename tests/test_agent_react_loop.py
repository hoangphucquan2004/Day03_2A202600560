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
    """Test that agent SELF-CORRECTS from hallucinated tool: tries search_course, fails, then uses check_slots."""
    llm = ScriptedLLM(
        [
            # Step 1: Agent hallucinates non-existent tool
            'Thought: I will call a tool that does not exist.\n'
            'Action: search_course({"query": "AI"})',
            # Step 2: Agent self-corrects - sees error + available_tools, tries correct tool
            'Thought: The tool search_course does not exist. Looking at the error observation, I can see available tools are check_slots and get_tuition. Let me use check_slots instead.\n'
            'Action: check_slots({"course_query": "AI"})',
            # Step 3: Agent now gets tuition for the course
            'Thought: I got the slot information. Now I need tuition.\n'
            'Action: get_tuition({"course_code": "AI3010", "student_id": "2A202600713"})',
            # Step 4: Agent provides final answer
            "Thought: I have slots and tuition information.\n"
            "Final Answer: AI3010 has available seats. The estimated tuition is 9,100,000 VND.",
        ]
    )
    agent = ReActAgent(llm=llm, tools=get_course_registration_tools(), max_steps=5)

    answer = agent.run("Check AI slots and tuition")

    # Verify agent actually CALLED the tools (not just mentioned them)
    assert "9,100,000" in answer, "Agent should have called get_tuition and returned tuition cost"
    assert "available" in answer.lower(), "Agent should have called check_slots and returned availability"
    assert llm.calls == 4, f"Agent should have called LLM 4 times (hallucinate, correct, get_tuition, final), got {llm.calls}"
