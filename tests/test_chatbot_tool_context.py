from typing import Any, Dict, Optional

from src.chatbot.chatbot import UniversityRegistrationChatbot
from src.core.llm_provider import LLMProvider


class CapturingLLM(LLMProvider):
    def __init__(self):
        super().__init__(model_name="capturing-llm")
        self.last_prompt = ""
        self.last_system_prompt = ""

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt or ""
        return {
            "content": "Tool-grounded chatbot response.",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "provider": "test",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None):
        yield self.generate(prompt, system_prompt)["content"]


def test_chatbot_includes_course_tool_context_in_prompt():
    llm = CapturingLLM()
    chatbot = UniversityRegistrationChatbot(llm=llm)

    answer = chatbot.chat("Tôi muốn đăng ký môn AI và Data Science, kiểm tra còn chỗ không và học phí tổng cộng?")

    assert answer == "Tool-grounded chatbot response."
    assert "TOOL CONTEXT:" in llm.last_prompt
    assert "AI3010" in llm.last_prompt
    assert "DATA3020" in llm.last_prompt
    assert "19150000" in llm.last_prompt
