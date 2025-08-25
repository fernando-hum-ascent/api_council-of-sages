## Dynamic Sages Plan

### Goal
Enable the system to use both:
- Predefined sages (curated, with tailored prompts), and
- Dynamically created sages (at runtime, defined by the moderator) using a generic role prompt.

The moderator will output a structure that selects from predefined sages and proposes new sages to create. The orchestrator will then run responses for all selected sages with the existing flow. The auxiliary_query step is removed for currently defined sages.

### Moderator Output (contract)
The moderator must return a JSON object with two fields:

```json
{
  "predefined_chosen_sages": ["marcus_aurelius", "strategy_expert"],
  "new_sages_to_create": [
    { "name": "Steve Jobs", "description": "Ex-Apple CEO focused on product vision" },
    { "name": "The financial expert", "description": "Personal finance and investing guidance" }
  ]
}
```

- predefined_chosen_sages: strictly uses keys from the predefined sages_registry.
- new_sages_to_create: list of objects with a minimal schema: name (string), description (string).

### Predefined Sages Registry
Provide a small in-code sages_registry used by the moderator and orchestrator:

```python
SAGES_REGISTRY = {
  "marcus_aurelius": {
    "description": "The roman emperor, useful for generic advice",
    "prompt_module": "marcus_aurelius_prompt",
  },
  "nassim_taleb": {
    "description": "The writer of Antifragile, useful for generic advice",
    "prompt_module": "nassim_taleb_prompt",
  },
  "strategy_expert": {
    "description": "Useful for planning questions: business, career, etc.",
    "prompt_module": null
  }
}
```

Notes:
- When prompt_module is present, use its tailored prompt. If null or missing, fallback to the generic role prompt using the sages_registry description.
- Keep sages_registry location close to `council_of_sages/orchestrator/prompt_modules/` or a small `sages_registry.py` to avoid cyclic imports.

### Orchestrator State & Types
Add a dynamic list of sages for a run. Suggested runtime-only schema:

```python
class SageSpec(BaseModel):
  source: Literal["predefined", "dynamic"]
  key: str | None  # for predefined keys (e.g., "marcus_aurelius")
  name: str        # display/role name (for prompts)
  description: str # short description to condition the role
  prompt_module: str | None  # if available for predefined
```

Graph state addition in `states.py` (conceptually):
- sages_to_run: list[SageSpec]

### Moderator Changes (`council_of_sages/orchestrator/moderator.py`)
- Update the system prompt to produce the exact JSON contract above (no auxiliary_query for predefined sages).
- Parse and validate the output into `list[SageSpec]` by:
  - Mapping predefined keys to `SageSpec(source="predefined", key=..., name=key, description=REGISTRY[key].description, prompt_module=REGISTRY[key].prompt_module)`
  - Mapping dynamic entries to `SageSpec(source="dynamic", key=None, name=item.name, description=item.description, prompt_module=None)`
- On validation failure, fallback to a minimal safe set (e.g., `strategy_expert`) and log.

### Prompts
- Keep tailored prompts for curated sages: `marcus_aurelius_prompt.py`, `nassim_taleb_prompt.py`, etc.
- Add a generic role prompt module (e.g., `role_sage_prompt.py`) that accepts parameters: `name`, `description`, `user_query`.
  - This generic prompt frames the assistant to “take the role of {name}” using the provided `description`.
  - Use it for any dynamic sage and as a fallback for predefined sages missing a tailored prompt.

### Orchestrator Flow (`graph_definition.py` / `llm_agent.py`)
High-level flow adjustments:
1. Moderator runs first and returns the JSON structure.
2. Build `sages_to_run: list[SageSpec]` from moderator output.
3. For each `SageSpec`:
   - If `prompt_module` is set, use it (tailored prompt path).
   - Else use the generic role prompt with `name` and `description`.
4. Collect all sage responses and continue with existing consolidation step.


### Removal: auxiliary_query
- The auxiliary_query used by current predefined prompts is deprecated and removed from the flow for those sages. Existing prompts should be updated accordingly to not expect auxiliary inputs.

### Billing & Usage Events
- Ensure token counting accounts for a dynamic number of parallel sage calls.
- No changes to external API. Internal events should include the `sage_name` to attribute costs and for analytics.

### Error Handling & Fallbacks
- If the moderator returns unknown predefined keys, drop them and log.
- If the moderator returns an empty set, fallback to `[strategy_expert]`.
- If any prompt fails, continue with others and still consolidate.

### Example End-to-End
User: "How should I frame my career path?"

Moderator output:
```json
{
  "predefined_chosen_sages": ["marcus_aurelius", "strategy_expert"],
  "new_sages_to_create": [
    { "name": "Steve Jobs", "description": "Product-focused CEO perspective" },
    { "name": "The financial expert", "description": "Career finance tradeoffs" }
  ]
}
```

Orchestrator runs 4 sages:
- marcus_aurelius (tailored prompt)
- strategy_expert (tailored prompt)
- Steve Jobs (generic role prompt)
- The financial expert (generic role prompt)

Then consolidate as today.

### Acceptance Criteria
- Moderator reliably returns the contract shape (validated in code).
- Orchestrator executes any number of sages (>=1) from a mix of predefined and dynamic.
- Tailored prompts are used when available; otherwise generic role prompt is used.
- Auxiliary_query is removed for predefined flows.
- Billing correctly reflects multiple sages.
