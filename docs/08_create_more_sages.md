## Create many sages at scale (adapted to current codebase)

This plan keeps your current separation:
- **`role_sage_prompt.py` remains unchanged** and is used only for dynamically created sages (on-the-fly).
- **Precreated sages** move to a simple, data-driven format (YAML) and use a single generic template for consistency.

### What exists today

- `role_sage_prompt.py` is the generic prompt used for dynamically created sages.
- `query_distribution_prompt.py` needs a human-readable list of available sages (id + description) and returns:
  - `predefined_chosen_sages`: list of ids (e.g., `"marcus_aurelius"`)
  - `new_sages_to_create`: list of `{name, description}` for dynamic sages

### Minimal, scalable approach for precreated sages

1) Store precreated sages as minimal YAML files under `council_of_sages/orchestrator/sages/`.
   - Schema kept simple as requested: `id`, `description`, `persona`.

```yaml
# council_of_sages/orchestrator/sages/marcus_aurelius.yaml
id: marcus_aurelius
description: The roman emperor, useful for generic advice
persona: |
  You are Marcus Aurelius, Roman Emperor and Stoic philosopher. Offer practical
  guidance grounded in Stoic principles applied to modern situations.
```

2) Keep a single generic template for precreated YAML-based sages (separate from `role_sage_prompt.py`).
   - Name suggestion: `predefined_sage_prompt.py`.
   - This template centralizes the common sections (Variables, Important) used by precreated sages.

```python
# council_of_sages/orchestrator/prompt_modules/predefined_sage_prompt.py
from ...lib.prompting import PromptModel

PREDEFINED_SAGE_PROMPT = PromptModel(
    prompt_name="predefined_sage",
    model="claude-3-5-haiku-20241022",
    json_format=False,
    temperature=0.3,
    template="""
<context>
# Purpose and Context
You are {id}. {description}
Respond from this established persona:
{persona}
</context>

<instructions>

# Response Guidelines
- Consider the conversation history to provide continuity
- Offer practical wisdom that can be applied to the user's situation
- Respond in 1-2 paragraphs with depth and insight

# Variables
- user message: {original_user_query}
- chat_context: {chat_context}

# Important:
- Always ensure you're actually addressing the user's question
- Answer in the same language as the user's message
</instructions>
""",
)
```

3) Add a tiny loader for YAML discovery and helpers. No previous `SAGES_REGISTRY` is needed.

```python
# council_of_sages/orchestrator/sages_loader.py (sketch)
from pathlib import Path
import yaml

SAGES_DIR = Path(__file__).parent / "sages"

def list_sage_ids() -> list[str]:
    return [p.stem for p in SAGES_DIR.glob("*.yaml")]

def load_sage_yaml(sage_id: str) -> dict:
    data = yaml.safe_load((SAGES_DIR / f"{sage_id}.yaml").read_text())
    return {
        "id": data["id"],
        "description": data["description"],
        "persona": data["persona"],
    }

def available_sages_text() -> str:
    lines: list[str] = []
    for sid in list_sage_ids():
        data = load_sage_yaml(sid)
        lines.append(f"- [{sid}] {data['description']}")
    return "\n".join(lines)

def build_prompt_for_predefined(
    sage_id: str, original_user_query: str, chat_context: str
) -> str:
    from council_of_sages.orchestrator.prompt_modules.predefined_sage_prompt import (
        PREDEFINED_SAGE_PROMPT,
    )
    data = load_sage_yaml(sage_id)
    return PREDEFINED_SAGE_PROMPT.render(
        id=data["id"],
        description=data["description"],
        persona=data["persona"],
        original_user_query=original_user_query,
        chat_context=chat_context,
    )
```

4) Keep `role_sage_prompt.py` exclusively for dynamic sages returned in `new_sages_to_create`.
   - You already pass `{name, description}` there; no changes needed.

### Wiring with `query_distribution_prompt.py`

- Build and pass `available_sages` as the list of `- [id] description` from the YAML loader:

```python
from council_of_sages.orchestrator.sages_loader import available_sages_text

available = available_sages_text()
prompt_vars = {
    "available_sages": available,
    "chat_context": chat_context,
    "user_query": user_query,
    "format_instructions": SAGE_SELECTION_PARSER.get_format_instructions(),
}
```

This ensures the model sees both the id and the human-readable description it needs to select `predefined_chosen_sages` correctly.

---
