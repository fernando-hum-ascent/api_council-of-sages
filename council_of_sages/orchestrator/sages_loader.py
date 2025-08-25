"""YAML-based sage loader for scalable sage management."""

from pathlib import Path
from typing import Any

import yaml

SAGES_DIR = Path(__file__).parent / "sages"


def list_sage_ids() -> list[str]:
    """List all available sage IDs from YAML files."""
    return sorted([p.stem for p in SAGES_DIR.glob("*.yaml")])


def load_sage_yaml(sage_id: str) -> dict[str, Any]:
    """Load sage data from YAML file."""
    yaml_path = SAGES_DIR / f"{sage_id}.yaml"
    if not yaml_path.exists():
        msg = f"Sage YAML file not found: {sage_id}.yaml"
        raise FileNotFoundError(msg)

    data = yaml.safe_load(yaml_path.read_text())
    return {
        "id": data["id"],
        "description": data["description"],
        "persona": data["persona"],
    }


def available_sages_text() -> str:
    """Generate human-readable list of available sages."""
    lines: list[str] = []
    # Exclude fallback-only sage from the selectable list
    selectable_sage_ids = [
        sid for sid in list_sage_ids() if sid != "generalist_sage"
    ]
    for i, sage_id in enumerate(selectable_sage_ids, 1):
        data = load_sage_yaml(sage_id)
        lines.append(f"{i}. **{sage_id}**: {data['description']}")
    return "\n".join(lines)


def available_sage_keys() -> str:
    """Generate comma-separated list of sage keys."""
    return ", ".join(list_sage_ids())


def build_prompt_for_predefined(
    sage_id: str, original_user_query: str, chat_context: str
) -> str:
    """Build formatted prompt for predefined sage using YAML data."""
    from .prompt_modules.predefined_sage_prompt import PREDEFINED_SAGE_PROMPT

    data = load_sage_yaml(sage_id)
    return PREDEFINED_SAGE_PROMPT.template.format(
        id=data["id"],
        description=data["description"],
        persona=data["persona"],
        original_user_query=original_user_query,
        chat_context=chat_context,
    )
