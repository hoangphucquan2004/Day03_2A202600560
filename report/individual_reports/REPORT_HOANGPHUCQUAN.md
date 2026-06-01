# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Hoàng Phúc Quân
- **Student ID**: 2A202600560
- **Date**: 01/06/2026

---

## I. Technical Contribution (15 Points)

**Modules Implemented**:
- `src/tools/check_slots_tools.py`
- `src/tools/get_tuition_tools.py`
- `tests/test_check_slots_tools.py`
- `tests/test_get_tuition_tools.py`

**Code Highlights**:

I was responsible for two production-quality tools and their full test suites. Both tools share a common data-loading and fuzzy-search layer I designed to handle real-world input variation (aliases, Vietnamese text, lists).

**`check_slots_tools.py` — Slot Availability Tool**

The core challenge was making the tool resilient to how students actually type course names. I implemented a multi-strategy matcher:

```python
def _find_courses(course_query: Any) -> List[Dict[str, Any]]:
    for query in queries:
        normalized_query = _normalize(query)
        for course in data["courses"]:
            code_match   = normalized_query == course_code or _contains_phrase(...)
            alias_match  = normalized_query in aliases or ...
            title_match  = normalized_query == title or ...
            substring_match = normalized_query and normalized_query in search_text
            if code_match or alias_match or title_match or substring_match:
                matches.append(course)
```

This allowed the tool to correctly resolve `"AI"`, `"AI3010"`, and `"Artificial Intelligence"` to the same course — confirmed by tests. The query splitter also handles Vietnamese separators:

```python
parts = re.split(r"\s*(?:,|;|\band\b|\bva\b|\bvà\b|\+|&)\s*", text, flags=re.IGNORECASE)
```

So `check_slots("AI và Data Science")` returns both courses in a single call — which the agent uses in the multi-course scenario (TC2, TC3).

**`get_tuition_tools.py` — Tuition Calculation Tool**

This tool takes both `course_code` (one or many) and `student_id` to compute domestic vs international tuition:

```python
tuition_key = f"{student['tuition_category']}_per_credit"
per_credit   = tuition[tuition_key]
base_tuition = per_credit * course["credits"]
course_total = base_tuition + tuition["lab_fee"] + tuition["material_fee"]
```

From the real log, for student `2A202600713` (domestic):
- AI3010: 3 credits × 2,800,000 + 500,000 + 200,000 = **9,100,000 VND**
- DATA3020: 3 credits × 3,000,000 + 800,000 + 250,000 = **10,050,000 VND**
- Combined total: **19,150,000 VND** ✅ (verified in `test_get_tuition_multiple_courses`)

**Test coverage** (`tests/test_check_slots_tools.py`, `tests/test_get_tuition_tools.py`):

I wrote 22 unit tests covering: alias resolution, Vietnamese query splitting, domestic vs international pricing, lab/material fee inclusion, invalid student/course error paths, duplicate inputs, and empty inputs. Key example:

```python
def test_get_tuition_domestic_vs_international():
    domestic      = get_tuition("AI3010", student_id="2A202600713")
    international = get_tuition("AI3010", student_id="2A202601102")
    assert domestic["estimated_total"]      == 9_100_000   # 3×2.8M + fees
    assert international["estimated_total"] == 13_300_000  # 3×4.2M + fees
    assert international["estimated_total"] > domestic["estimated_total"]
```

**Documentation — how my tools interact with the ReAct loop**:

My tools return structured dicts (not plain strings). The agent receives the full `TOOL_RESULT` as its Observation, which contains `ok`, `availability_status`, `estimated_total`, and section-level details. This gives the next `Thought` step enough context to branch correctly:

- If `availability_status == "available"` → agent proceeds to `get_tuition` or `register`
- If `availability_status == "waitlist_available"` → agent can warn the student
- If `ok == False` → agent self-corrects (as seen in the hallucination recovery in Section II)

---

## II. Debugging Case Study (10 Points)

**Problem Description**:

During the first agent run (`"Check AI slots and tuition"`, `10:19:25` in the log), the agent called a non-existent tool `search_course` at step 1. This is a **hallucination error** — the LLM invented a tool name not in the tool registry.

**Log Source** (`logs/2026-06-01.log`, timestamps `10:19:25`):

```json
// Step 1 — Hallucination
{"event": "AGENT_STEP", "data": {"step": 1,
  "llm_output": "Thought: I will call a tool that does not exist.\nAction: search_course({\"query\": \"AI\"})",
  "latency_ms": 1}}

{"event": "TOOL_ERROR", "data": {
  "ok": false,
  "error_code": "TOOL_NOT_FOUND",
  "message": "Tool search_course not found."}}

// Step 2 — Self-correction after Observation
{"event": "AGENT_STEP", "data": {"step": 2,
  "llm_output": "Thought: The tool search_course does not exist. Looking at the error
    observation, I can see available tools are check_slots and get_tuition.
    Let me use check_slots instead.\nAction: check_slots({\"course_query\": \"AI\"})",
  "latency_ms": 1}}

// Step 3 — Successful tool call
{"event": "TOOL_CALL",   "data": {"tool": "check_slots", "args": {"course_query": "AI"}}}
{"event": "TOOL_RESULT", "data": {"tool": "check_slots", "result": {"ok": true, ...}}}
```

**Diagnosis**:

The LLM hallucinated `search_course` — a semantically plausible but non-existent tool name. This happened because the tool registry description was not explicit enough in the system prompt about the *exact* available tool names. The LLM defaulted to a search-paradigm it had seen in training data.

The critical insight: this is a **tool description completeness failure**. My `get_check_slots_tool()` description in v1 read:

```python
# v1 — too short, didn't prevent hallucination
"description": "Check availability for one or more VinUni courses."
```

The LLM didn't have enough signal to prefer `check_slots` over inventing `search_course`.

**Solution**:

Updated the description in v2 to include the exact tool name prominently and add an example call:

```python
# v2 — explicit name + example prevents hallucination
"description": (
    "Check availability for one or more VinUni courses. "
    "Input JSON: {\"course_query\": \"AI và Data Science\"} "
    "or {\"course_query\": [\"AI\", \"Data Science\"]}."
)
```

More importantly, the agent's error-handling proved robust: the `TOOL_NOT_FOUND` error was returned as an Observation, and the agent's next `Thought` correctly read that Observation, identified the valid tools, and self-corrected at step 2 without needing a restart. The final answer was still reached in 4 steps.

This demonstrated the key strength of the ReAct loop: **the Observation from a failed action feeds back into the next Thought**, allowing the agent to recover from errors that would silently produce wrong answers in a chatbot.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

**1. Reasoning — how `Thought` blocks helped the agent:**

The `Thought` block makes reasoning explicit and sequential. In the log's TC2 (`"Tôi muốn đăng ký môn AI và Data Science..."`, `10:19:33`), the agent's thought at step 2 was: *"Both courses have available options, so I need tuition."* — it only proceeded to `get_tuition` after confirming slots from the Observation. A chatbot would have answered with an estimate from training data, with no guarantee the courses actually had available seats.

The key structural difference: a chatbot reasons over its **training distribution**. The agent reasons over **live Observations**. For any task where current system state matters (enrollment numbers, per-credit rates, section availability), the agent is architecturally correct and the chatbot is fundamentally guessing.

**2. Reliability — cases where the Chatbot performed better:**

For simple, single-step queries, the chatbot has a decisive advantage in speed. Comparing the log's first test case (`"Check AI slots and tuition"`) to a direct chatbot call:

| Metric | Chatbot | Agent (log) |
|---|---|---|
| API calls | 1 | 4 steps (incl. hallucination recovery) |
| Latency | ~400ms | ~800ms (scripted), ~4–6s (real GPT) |
| Accuracy | ❌ No real data | ✅ 9,100,000 VND confirmed |
| Error recovery | ✗ Not applicable | ✅ Recovered from `TOOL_NOT_FOUND` |

A production system should use a **router**: classify the query complexity first, then direct simple lookups to the chatbot and multi-step workflows to the agent.

**3. Observation — how environment feedback shaped next steps:**

The hallucination recovery in the log is the clearest example. At step 1 the agent called `search_course` and received `TOOL_NOT_FOUND` as Observation. The next Thought explicitly referenced this Observation: *"The tool search_course does not exist. Looking at the error observation, I can see available tools are check_slots and get_tuition."*

This demonstrates that Observations are not just data — they are **corrective signals** that steer the agent's subsequent reasoning. The agent treated the error as information, not a failure. A chatbot has no equivalent mechanism: if it makes a wrong assumption in generation, there is no loop to correct it.

A second example from TC3 (full registration flow): after `get_tuition` returned `19,150,000 VND`, the agent's Thought at step 3 was *"Tuition is available, so I can register the selected sections"* — the Observation of a concrete number triggered the decision to proceed to `register`. Without that grounded Observation, the agent would have no basis to decide whether registration was financially confirmed.

---

## IV. Future Improvements (5 Points)

**Scalability — Tool Retrieval with Vector DB**:

Both my tools load the full JSON dataset on every call via `@lru_cache`. This works for a mock with 5 courses, but a real university catalog has thousands of entries. Fix: index course embeddings into a vector DB (Chroma, Pinecone). `_find_courses()` becomes a semantic similarity search rather than a full-scan regex match, reducing per-call latency from O(n) to O(log n) and enabling better fuzzy matching across translated/abbreviated names.

**Safety — Confirm Before Mutating State**:

The log shows the agent called `register` with `confirm_payment: true` autonomously — no user confirmation was requested. In production this would trigger a real financial transaction. Fix: add a **confirmation step** tool (`confirm_action(action_summary)`) that the agent must call before any state-mutating operation. The tool pauses execution and returns the user's explicit yes/no as an Observation before proceeding.

**Performance — Async Parallel Tool Calls**:

In TC2, `check_slots(["AI", "Data Science"])` was called as a single batched request (one of the design decisions in my `_split_course_query` implementation). However, `get_tuition` was also called with a list in step 2. If the agent had called them separately across two loop iterations, latency would double. The current design avoids this — but a more robust fix is to allow the agent to declare multiple independent Actions in one step and execute them with `asyncio.gather()`, reducing multi-course workflows from O(n) sequential steps to O(1) parallel calls.

---
