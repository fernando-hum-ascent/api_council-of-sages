from pydantic import BaseModel, Field


class PromptModel(BaseModel):
    model: str = Field(
        ..., description="The model to be used for evaluating the prompt"
    )
    json_format: bool = Field(
        ..., description="Should the returned response be a dictionary?"
    )
    template: str = Field(..., description="The prompt content")
    temperature: float | None = Field(
        default=0.7,
        description=(
            "The temperature to use for generating the response (between 0 "
            "and 1)"
        ),
        ge=0,
        le=1,
    )
    validation_n: int | None = Field(
        default=30, description="The prompt to be tested on n samples"
    )
    validation_success_rate: float | None = Field(
        default=0.90,
        description=(
            "The minimum acceptable success rate for validation (between 0 "
            "and 1)"
        ),
        ge=0,
        le=1,
    )
    prompt_name: str | None = Field(
        default="prompt without name",
        description="The name (identifier) for the prompt",
    )
