# Temporarily disabled parsers due to parsing issues
from .marcus_aurelius_prompt import (
    # MARCUS_AURELIUS_PARSER,  # noqa: ERA001
    MARCUS_AURELIUS_PROMPT,
)
from .nassim_taleb_prompt import (
    # NASSIM_TALEB_PARSER,  # noqa: ERA001
    NASSIM_TALEB_PROMPT,
)
from .naval_ravikant_prompt import (
    # NAVAL_RAVIKANT_PARSER,  # noqa: ERA001
    NAVAL_RAVIKANT_PROMPT,
)
from .query_distribution_prompt import (
    QUERY_DISTRIBUTION_PARSER,
    QUERY_DISTRIBUTION_PROMPT,
)
from .response_consolidation_prompt import RESPONSE_CONSOLIDATION_PROMPT

__all__ = [
    "MARCUS_AURELIUS_PROMPT",
    # "MARCUS_AURELIUS_PARSER",  # noqa: ERA001
    "NASSIM_TALEB_PROMPT",
    # "NASSIM_TALEB_PARSER",  # noqa: ERA001
    "NAVAL_RAVIKANT_PROMPT",
    # "NAVAL_RAVIKANT_PARSER",  # noqa: ERA001
    "QUERY_DISTRIBUTION_PROMPT",
    "QUERY_DISTRIBUTION_PARSER",
    "RESPONSE_CONSOLIDATION_PROMPT",
]
