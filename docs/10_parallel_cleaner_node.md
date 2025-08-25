### Parallel cleaner node: remove explicit sage references from user input

Goal: add a `clean_user_input_node` that rewrites the user query to remove any explicit references to particular sages/people (e.g., "Please include Charlie Munger"). This node should run in parallel with `sage_selection`, and the cleaned text should be used as the input for the sages in `parallel_sages`.

---

### 1) Extend orchestrator state
Add a new optional field `cleaned_user_query` to the orchestrator state.

Edit `council_of_sages/orchestrator/states.py`:

```python
class OrchestratorState(TypedDict):
    # ... existing fields ...
    cleaned_user_query: str | None  # Cleaned version of the user_query for sages
```

Notes:
- Keep `user_query` unchanged for selection and logging.
- We will fall back to `user_query` when `cleaned_user_query` is not present.

---

### 2) Create cleaner prompt/model in prompt_modules
Define the prompt and model in a dedicated module under `prompt_modules/`, following the existing pattern.

Create `council_of_sages/orchestrator/prompt_modules/user_input_cleaner_prompt.py`:

```python
# ruff: noqa: E501
from ...lib.prompting import PromptModel

USER_INPUT_CLEANER_PROMPT = PromptModel(
    prompt_name="user_input_cleaner",
    model="claude-3-5-haiku-20241022",  # lightweight & inexpensive
    json_format=False,
    temperature=0.0,  # deterministic cleaning
    template=(
        "You are a careful editor. Remove any request to include or quote specific "
        "people, personas, or named sages from the user's text. Preserve the intent "
        "and wording of the underlying question. Return ONLY the cleaned question, "
        "without quotes or extra commentary.\n\n"
        "Original: {user_query}\n"
        "Cleaned:"
    ),
)
```

Export it in `council_of_sages/orchestrator/prompt_modules/__init__.py`:

```python
from .user_input_cleaner_prompt import USER_INPUT_CLEANER_PROMPT

__all__ = [
    # ... existing exports ...
    "USER_INPUT_CLEANER_PROMPT",
]
```

---

### 3) Implement the cleaner node (imports prompt/model)
Define a new async node in `council_of_sages/orchestrator/graph_definition.py` that uses the prompt/model above, wrapped by the billing proxy.

```python
from langchain_anthropic import ChatAnthropic
from ..lib.billing.billing_llm_proxy import BillingLLMProxy
from .prompt_modules import USER_INPUT_CLEANER_PROMPT


async def clean_user_input_node(state: OrchestratorState) -> dict[str, Any]:
    """Rewrite the user query removing explicit requests to include names of
    sages/personas/people. Return only the cleaned question.

    Example:
      In:  "Should I try to beat the market? Please include Charlie Munger"
      Out: "Should I try to beat the market?"
    """
    user_query = state["user_query"]

    # LLM from prompt module + billing
    raw_llm = ChatAnthropic(
        model=USER_INPUT_CLEANER_PROMPT.model,
        temperature=USER_INPUT_CLEANER_PROMPT.temperature,
    )
    llm = BillingLLMProxy(raw_llm)

    formatted_prompt = USER_INPUT_CLEANER_PROMPT.template.format(
        user_query=user_query
    )

    try:
        response = await llm.ainvoke(formatted_prompt)
        cleaned = str(getattr(response, "content", "")).strip()
        cleaned = cleaned.strip().rstrip("\"")

        return {
            "cleaned_user_query": cleaned if cleaned else user_query,
            "moderator_responses": {
                **state.get("moderator_responses", {}),
                "cleaning": {
                    "original_len": len(user_query),
                    "cleaned_len": len(cleaned) if cleaned else len(user_query),
                },
            },
        }
    except Exception as e:  # noqa: BLE001
        # Fail open by returning original query
        return {
            "cleaned_user_query": user_query,
            "moderator_responses": {
                **state.get("moderator_responses", {}),
                "cleaning": {"error": str(e)},
            },
        }
```

Notes:
- Prompt and model are centralized in `prompt_modules/` for consistency.
- `json_format` is False; the node expects plain text output.

---

### 4) Wire the graph to run cleaner in parallel with selection
We will fork from `START` to both `sage_selection` and `clean_user_input`, and then join into `parallel_sages`. This ensures `parallel_sages` receives both `sages_to_run` and `cleaned_user_query`.

Edit `council_of_sages/orchestrator/graph_definition.py` (imports and wiring):

```python
from langgraph.graph import START, END, StateGraph

# ... keep node registrations ...

builder = StateGraph(OrchestratorState)

# Add nodes
builder.add_node("sage_selection", sage_selection_node)
builder.add_node("clean_user_input", clean_user_input_node)
builder.add_node("parallel_sages", parallel_sages_node)
builder.add_node("consolidation", consolidation_node)

# Fork at START so both nodes run concurrently
builder.add_edge(START, "sage_selection")
builder.add_edge(START, "clean_user_input")

# Join before parallel_sages (it will await both parents)
builder.add_edge("sage_selection", "parallel_sages")
builder.add_edge("clean_user_input", "parallel_sages")

# Then consolidation and END
builder.add_edge("parallel_sages", "consolidation")
builder.add_edge("consolidation", END)

orchestrator_graph = builder.compile()
```

Notes:
- Replace the previous `set_entry_point("sage_selection")` and the direct edge from `sage_selection` to `parallel_sages` with the fork/join structure above.
- Import `START` in addition to `END`.

---

### 5) Use the cleaned query when executing sages
Update `parallel_sages_node` to use the cleaned text.

Edit `council_of_sages/orchestrator/graph_definition.py` (inside `parallel_sages_node`):

```python
sages_to_run = limit_sages_to_run(state.get("sages_to_run", []), state)
user_query = cast(str, state.get("cleaned_user_query") or state["user_query"])  # prefer cleaned
chat_history = state.get("chat_history", [])
```

This ensures sages receive a version of the question without explicit persona injection, while selection still sees the original request to make a good choice of sages.

---

### 6) Example
Input: `Should I try to beat the market? Please include Charlie Munger`
- `sage_selection` sees the original text (can choose relevant investing sages).
- `clean_user_input` produces: `Should I try to beat the market?`
- `parallel_sages` runs sages using the cleaned question.
- `consolidation` combines the sages' answers.

---

### 7) Validation
- Type checkers: `cleaned_user_query` is optional; code falls back to `user_query`.
- Concurrency: LangGraph will merge the independent state updates from the two branches and only proceed to `parallel_sages` once both are done.
- Billing: Cleaner node uses the same billing proxy as other LLM calls.
