import inspect
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

class ReActAgent:
    """
    SKELETON: A ReAct-style Agent that follows the Thought-Action-Observation loop.
    Students should implement the core loop logic and tool execution.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []

    def get_system_prompt(self) -> str:
        """
        System prompt that instructs the agent to follow ReAct.
        Should include:
        1.  Available tools and their descriptions.
        2.  Format instructions: Thought, Action, Observation.
        """
        tool_descriptions = "\n".join(
            [f"- {t['name']}: {t['description']}" for t in self.tools]
        )
        return f"""
You are a VinUniversity course registration assistant.
You have access to the following tools:
{tool_descriptions}

Use the following format exactly:
Thought: your line of reasoning.
Action: tool_name({{"argument_name": "argument_value"}})
Observation: result of the tool call.
... (repeat Thought/Action/Observation if needed)
Final Answer: your final response.

Rules:
- Use raw JSON inside Action parentheses.
- Call tools before answering questions about slots, tuition, or registration data.
- If a tool returns errors, explain the issue instead of inventing data.
"""

    def run(self, user_input: str) -> str:
        """
        Implement the ReAct loop logic.
        1. Generate Thought + Action.
        2. Parse Action and execute Tool.
        3. Append Observation to prompt and repeat until Final Answer.
        """
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})

        current_prompt = f"Question: {user_input}"
        steps = 0

        while steps < self.max_steps:
            result = self.llm.generate(current_prompt, system_prompt=self.get_system_prompt())
            content = result.get("content", "")
            self.history.append({"role": "assistant", "content": content})

            logger.log_event(
                "AGENT_STEP",
                {
                    "step": steps + 1,
                    "llm_output": content,
                    "latency_ms": result.get("latency_ms", 0),
                },
            )
            if "usage" in result:
                tracker.track_request(
                    provider=result.get("provider", "unknown"),
                    model=self.llm.model_name,
                    usage=result.get("usage", {}),
                    latency_ms=result.get("latency_ms", 0),
                )

            final_answer = self._parse_final_answer(content)
            if final_answer:
                logger.log_event("AGENT_END", {"steps": steps + 1, "status": "final_answer"})
                return final_answer

            action = self._parse_action(content)
            if action is None:
                observation = json.dumps(
                    {
                        "ok": False,
                        "error_code": "PARSER_ERROR",
                        "message": "No valid Action found. Use Action: tool_name({\"arg\": \"value\"}).",
                    }
                )
                logger.log_event("AGENT_PARSE_ERROR", {"step": steps + 1, "output": content})
            else:
                tool_name, args = action
                observation = self._execute_tool(tool_name, args)

            current_prompt = f"{current_prompt}\n{content}\nObservation: {observation}"
            steps += 1

        logger.log_event("AGENT_END", {"steps": steps, "status": "max_steps_exceeded"})
        return "I could not finish the registration task within the allowed reasoning steps."

    def _parse_final_answer(self, text: str) -> Optional[str]:
        match = re.search(r"Final Answer\s*:\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        return match.group(1).strip()

    def _parse_action(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        match = re.search(
            r"Action\s*:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)\s*$",
            text.strip(),
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None

        tool_name = match.group(1)
        raw_args = match.group(2).strip()
        if not raw_args:
            return tool_name, {}

        try:
            parsed_args = json.loads(raw_args)
        except json.JSONDecodeError:
            parsed_args = self._parse_key_value_args(raw_args)

        if not isinstance(parsed_args, dict):
            parsed_args = {"value": parsed_args}

        return tool_name, parsed_args

    def _parse_key_value_args(self, raw_args: str) -> Dict[str, Any]:
        args: Dict[str, Any] = {}
        for item in raw_args.split(","):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            args[key.strip()] = value.strip().strip("\"'")
        return args

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        Helper method to execute tools by name.
        """
        for tool in self.tools:
            if tool['name'] == tool_name:
                try:
                    function = tool["function"]
                    signature = inspect.signature(function)
                    accepted_args = {
                        key: value
                        for key, value in args.items()
                        if key in signature.parameters
                    }
                    logger.log_event("TOOL_CALL", {"tool": tool_name, "args": accepted_args})
                    result = function(**accepted_args)
                    logger.log_event("TOOL_RESULT", {"tool": tool_name, "result": result})
                    return json.dumps(result, ensure_ascii=False)
                except Exception as exc:
                    error = {
                        "ok": False,
                        "error_code": "TOOL_EXECUTION_ERROR",
                        "tool": tool_name,
                        "message": str(exc),
                    }
                    logger.log_event("TOOL_ERROR", error)
                    return json.dumps(error, ensure_ascii=False)

        error = {
            "ok": False,
            "error_code": "TOOL_NOT_FOUND",
            "message": f"Tool {tool_name} not found.",
        }
        logger.log_event("TOOL_ERROR", error)
        return json.dumps(error, ensure_ascii=False)
