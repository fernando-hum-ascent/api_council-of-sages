## Small adjustments to the council conversation

### Goal
- Add original user query into each sage's prompt (not only the moderator-crafted sub-query).
- Make each sage return a structured result: { answer, summary }.
- Persist the summary and use summaries to build conversation history for future sage prompts.

### Current flow (high-level)
- Query distribution builds targeted prompts per sage and stores them in state as `agent_queries`.
```1:26:council_of_sages/orchestrator/graph_definition.py
async def query_distribution_node(
    state: OrchestratorState,
) -> dict[str, dict[str, str]]:
    """Moderator analyzes user query with conversation context and creates
    specific queries for each sage"""
    moderator = ResponseModerator()
    user_query = state["user_query"]
    chat_history = state.get("chat_history", [])

    sage_queries = await moderator.distribute_query(user_query, chat_history)
    return {"agent_queries": sage_queries}
```

- Selected sages are run in parallel with `philosophical_sage` using the moderator's query, and the raw string outputs are returned as `agent_responses`.
```39:81:council_of_sages/orchestrator/graph_definition.py
for sage in available_sages:
    if sage in agent_queries:
        tasks.append(
            philosophical_sage.ainvoke(
                {
                    "sage": sage,
                    "query": agent_queries[sage],
                    "state": state,
                }
            )
        )
        sage_names.append(sage)
...
results = await asyncio.gather(*tasks, return_exceptions=True)
sage_responses = {}
for i, result in enumerate(results):
    if isinstance(result, Exception):
        sage_responses[sage_names[i]] = f"Error: {str(result)}"
    else:
        sage_responses[sage_names[i]] = str(result)
return {"agent_responses": sage_responses}
```

- The sage tool formats a prompt with `{query}` and `{chat_context}` only; it does not include the original user query. It returns a decorated string.
```69:113:council_of_sages/orchestrator/tools/philosophical_sage.py
async def philosophical_sage_function(
    sage: SageEnum, query: str, state: OrchestratorState
) -> str:
    ...
    chat_history = state.get("chat_history", [])
    ...
    formatted_prompt = prompt_model.template.format(
        query=query, chat_context=chat_context
    )
    response = await llm.ainvoke(formatted_prompt)
    sage_response = f"""{config["response_header"]}

{response.content}
"""
    return sage_response
```

- Conversation persistence saves the consolidated response only; chat history is built from the raw `content` of messages (stringified if dict).
```155:173:council_of_sages/orchestrator/llm_agent.py
async def save_conversation_messages(
    conversation: "Conversation", user_query: str, ai_response: str
) -> None:
    ...
    await conversation.add_message(user_query, ChatUserEnum.human)
    await conversation.add_message(ai_response, ChatUserEnum.ai)
```
```63:73:council_of_sages/models/conversations.py
def get_chat_history(self) -> list[tuple[str, str]]:
    chat_history = []
    for message in self.messages:
        role = "human" if message.role == ChatUserEnum.human else "ai"
        content = message.content
        if isinstance(content, dict):
            content = str(content)
        chat_history.append((role, content))
    return chat_history
```

### Required changes (plan)

#### 1) Include original user query in each sage prompt
- Update prompt templates to accept `{original_user_query}` in addition to `{query}` and `{chat_context}`:
  - `council_of_sages/orchestrator/prompt_modules/marcus_aurelius_prompt.py`
  - `council_of_sages/orchestrator/prompt_modules/nassim_taleb_prompt.py`
  - `council_of_sages/orchestrator/prompt_modules/naval_ravikant_prompt.py`
  - Add a short note in each template instructing to reconcile both signals: the moderator-focused sub-query and the original user question.

- Update `philosophical_sage_function` to pass the new variable:
  - Read original user query from `state["user_query"]`.
  - Format: `prompt_model.template.format(query=query, original_user_query=state["user_query"], chat_context=chat_context)`.

Notes:
- Keep using the last N messages for `chat_context` as today. This will be adjusted in step (3) to rely on summaries.

#### 2) Make each sage return structured output: { answer, summary }
- Create a Pydantic model for sage outputs:
  - File: `council_of_sages/types.py`
  - Add `class SageResponse(BaseModel): answer: str; summary: str`.
  - Optionally add `sage: SageEnum` for traceability if helpful.

- Adjust sage prompt modules to return JSON:
  - Set `json_format=True` in the three sage `PromptModel`s, and append explicit JSON response instructions with keys `answer` and `summary`.
  - Keep temperature/model as-is.

- Update `philosophical_sage_function`:
  - Use `PydanticOutputParser` with `SageResponse`.
  - Build `format_instructions = parser.get_format_instructions()` and inject into the prompt, or append a strict JSON section to the template.
  - Parse `response.content` into `SageResponse` and return it as a dict (or the Pydantic model instance). Remove string decoration headers/footers.

- Update graph handling of responses:
  - In `parallel_sages_node`, collect `SageResponse` objects instead of strings.
  - Iterate dynamically over the keys in `agent_queries` to spawn tasks and collate results (do not hardcode sage names).
  - Set `sage_responses[sage_name] = result` where `result` is already a dict/Pydantic model.
  - Update `OrchestratorState` typing to reflect `agent_responses: dict[str, SageResponse]`.
  - Update API response typing in `OrchestratorResponse.agent_responses` to `dict[str, SageResponse]`.

- Update consolidation to work with structured outputs:
  - `ResponseModerator.consolidate_responses(...)` currently expects strings. Update the prompt `RESPONSE_CONSOLIDATION_PROMPT` to accept two separate variables derived from `agent_responses`:
    - `sage_answers` (map of sage -> answer)
    - `sage_summaries` (map of sage -> summary)
  - In code, transform `agent_responses` into those two maps before formatting the consolidation prompt.
  - Keep the final output as a single consolidated natural-language `final_response`.

#### 3) Persist per-sage summaries and use them for future chat history
- Do not store a consolidated message. The consolidated answer is only for the API/frontend and can be reconstructed client-side from per-sage messages if needed.

- Update conversation persistence API:
  - Change `save_conversation_messages(conversation, user_query, agent_responses)` so it creates one `ai` message per sage dynamically (iterate over `agent_responses.items()`), each with content like:
    ```json
    {
      "type": "sage_output",
      "sage": "<dynamic-sage-id>",
      "answer": "...",
      "summary": "...",
      "turn_id": "<uuid-for-this-interaction>"
    }
    ```
  - This fits the existing `Message.content: str | dict` field without schema changes and is streaming-friendly.
  - Also store the human message for the same interaction with the same `turn_id` in its content (e.g., `{ "type": "user_query", "turn_id": "...", "text": "..." }`) to enable grouping without schema changes.

- Turn identifier (turn_id) generation and propagation:
  - Create `turn_id = str(uuid.uuid4())` once per request in `arun_agent`, immediately after obtaining the conversation and before building the state.
  - Extend `build_orchestrator_state` to accept and store `turn_id` in the `OrchestratorState`.
  - Persist the human message with this `turn_id`.
  - Persist each per-sage AI message with the same `turn_id`.
  - For streaming, use the same `turn_id` to pre-create and later update each sage’s AI message.

- Make chat history use only summaries when present:
  - Update `Conversation.get_chat_history()`:
    - Retrieve only the last 3 interactions, where one interaction is defined as one human message followed by N AI messages that share the same `turn_id` (or by scanning from a human message to just before the next human message if `turn_id` is missing for legacy data).
    - For human messages: keep the plain text (or `content.text` if dict).
    - For AI messages: if `content` is a dict and contains a `summary`, use it; otherwise fallback to stringifying `content`.
  - This ensures subsequent sage prompts see compact, focused memory from only the most recent context, independent of which sages were selected.

- Update `philosophical_sage_function` chat context:
  - No change needed once `get_chat_history()` emits summaries; it will automatically pull summary-only context from state.

#### 4) Schema and typing updates
- `council_of_sages/orchestrator/states.py`:
  - Update `OrchestratorState` types for `agent_responses` to structured `SageResponse`.
  - Add `turn_id: str` to the state so nodes and tools can access it if needed.

- `council_of_sages/types.py`:
  - Add `SageResponse` model.
  - Update `OrchestratorResponse.agent_responses` type accordingly.

- Data model: separate `Message` from `Conversation`:
  - Replace embedded `messages: List[Message]` with a top-level `Message` document that references a conversation via `conversation_id` (string or `ReferenceField`).
  - `Message` fields: `id`, `conversation_id`, `role` (human|ai), `content` (DynamicField), `timestamp`, `turn_id` (str), optional `sage` (SageEnum), optional `type` (e.g., `sage_output`, `user_query`).
  - Indexes: `(conversation_id, -timestamp)`, `(conversation_id, turn_id, -timestamp)`, optional `(conversation_id, role)`.
  - `get_chat_history` should query the `Message` collection by `conversation_id`, sort by `timestamp` desc/asc as needed, then select the last 3 interactions (grouped by `turn_id` when available) and emit summaries.

Notes:
- No schema changes required to support interactions: keep `Message.content` as `DynamicField` and embed `turn_id` within content for both human and AI messages. This is sufficient for grouping and for future streaming.

#### 5) Backward compatibility and fallbacks
- `Conversation.get_chat_history()` must handle historical conversations where AI `content` is a plain string; keep the current fallback behavior.
- In `parallel_sages_node`, if a sage invocation throws, return `{ "answer": "Error: ...", "summary": "Error invoking sage." }` for that sage so downstream code remains consistent.
- Keep `distribute_query` unchanged; its output is still a map of sage -> sub-query. We only add the `original_user_query` at the sage prompt level.

#### 6) Testing checklist
- Unit tests (or manual smoke) for:
  - Sage prompt includes `original_user_query`.
  - `philosophical_sage_function` returns `SageResponse` shape and is parsed.
  - `parallel_sages_node` aggregates structured responses.
  - Consolidation consumes `sage_answers` and optionally `sage_summaries` correctly.
  - `save_conversation_messages` stores one AI message per sage with `{answer, summary}`.
  - `get_chat_history` returns only the last 3 interactions and emits summaries when present; falls back gracefully for legacy messages.

### Implementation order (suggested)
1) Define `SageResponse` in `types.py` and update `states.py` + `OrchestratorResponse` types.
2) Update sage prompt templates to include `{original_user_query}` and JSON response instructions; set `json_format=True`.
3) Create a top-level `Message` model and switch reads/writes from embedded messages to the `Message` collection.
4) Generate `turn_id` in `arun_agent`, extend `build_orchestrator_state` to include it, and thread it through persistence.
5) Update `philosophical_sage_function` to pass `original_user_query`, parse to `SageResponse`, and return structured data.
6) Update `parallel_sages_node` to iterate dynamically over `agent_queries` keys, handle structured results, and fallback errors to structured shape.
7) Update consolidation to consume `sage_answers`/`sage_summaries` and keep returning a single consolidated string (not persisted).
8) Update persistence to write one human `Message` and one AI `Message` per sage (all with the same `turn_id`).
9) Implement `get_chat_history` using the `Message` collection to return summaries for the last 3 interactions (grouped by `turn_id` when present).
10) Adapt API response typing and verify client compatibility.

### Notes on billing
- No changes needed in `BillingLLMProxy`; it will count tokens on JSON inputs/outputs just like strings.

### Acceptance criteria
- Sage prompts receive both the original user query and the moderator sub-query.
- `agent_responses` are structured with `answer` and `summary`.
- Conversation persistence stores summaries.
- Future turns feed summaries (not full answers) as chat context to sages.
