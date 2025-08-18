import uuid
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from loguru import logger

from .costs import is_model_supported
from .service import (
    log_failed_usage,
    perform_pre_request_checks,
    process_billing,
)


class BillingLLMProxy:
    """Proxy that wraps LLM clients to handle billing automatically"""

    def __init__(self, base_llm: BaseLanguageModel) -> None:
        """Initialize billing proxy

        Args:
            base_llm: Base LLM client to wrap

        Raises:
            ValueError: If model cannot be inferred or is not supported
        """
        self.base_llm = base_llm
        self.model_name = self._infer_model_name()

        if not is_model_supported(self.model_name):
            raise ValueError(
                f"Model '{self.model_name}' is not supported. "
                "Please check the pricing configuration."
            )

    def _infer_model_name(self) -> str:
        """Infer model name from base LLM client

        Returns:
            Model name

        Raises:
            ValueError: If model name cannot be inferred
        """
        # Try common LangChain model attributes
        for attr in ["model", "model_name", "model_id"]:
            model = getattr(self.base_llm, attr, None)
            if model:
                return str(model)

        # Try nested configuration
        if hasattr(self.base_llm, "model_kwargs"):
            model = self.base_llm.model_kwargs.get("model")
            if model:
                return str(model)

        raise ValueError(
            f"Cannot infer model name from {type(self.base_llm)}. "
            "Please set the model attribute on the base LLM client."
        )

    async def _pre_request_checks(self) -> str:
        """Perform pre-request checks

        Returns:
            User ID from context

        Raises:
            HTTPException: If user not authenticated or insufficient funds
        """
        return await perform_pre_request_checks()

    def _extract_input_content(
        self, *args: Any, **kwargs: Any
    ) -> str | list[dict[str, Any]]:
        """Extract input content from invoke arguments

        Returns:
            Input content for token counting
        """
        # Handle different invoke patterns
        if args:
            first_arg = args[0]
            if isinstance(first_arg, str):
                return first_arg
            elif isinstance(first_arg, list) and all(
                isinstance(msg, dict | BaseMessage) for msg in first_arg
            ):
                # Convert BaseMessage to dict format if needed
                messages = []
                for msg in first_arg:
                    if isinstance(msg, BaseMessage):
                        messages.append(
                            {
                                "role": msg.__class__.__name__.lower().replace(
                                    "message", ""
                                ),
                                "content": msg.content,
                            }
                        )
                    else:
                        messages.append(msg)
                return messages

        # Check kwargs
        for key in ["input", "prompt", "messages"]:
            if key in kwargs:
                return kwargs[key]

        # Fallback
        logger.warning(
            f"Could not extract input content from args={args}, "
            f"kwargs={kwargs}"
        )
        return str(args) + str(kwargs)

    def _extract_output_content(self, result: Any) -> str:
        """Extract output content from result

        Args:
            result: LLM result

        Returns:
            Output content string
        """
        # Handle different result types
        if isinstance(result, str):
            return result
        elif hasattr(result, "content"):
            return str(result.content)
        elif isinstance(result, LLMResult):
            # LangChain LLMResult
            if result.generations and result.generations[0]:
                return result.generations[0][0].text

        # Fallback to string representation
        return str(result)

    def _extract_response_metadata(self, result: Any) -> dict[str, Any] | None:
        """Extract response metadata for token counting

        Args:
            result: LLM result

        Returns:
            Response metadata if available
        """
        if hasattr(result, "response_metadata"):
            return result.response_metadata
        elif isinstance(result, LLMResult) and result.llm_output:
            return result.llm_output
        return None

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        """Async invoke with billing

        Returns:
            LLM result with billing handled transparently
        """
        # Pre-request checks
        user_id = await self._pre_request_checks()
        request_id = str(uuid.uuid4())

        # Extract input for token counting
        input_content = self._extract_input_content(*args, **kwargs)

        try:
            # Call base LLM
            result = await self.base_llm.ainvoke(*args, **kwargs)

            # Extract output and metadata
            output_content = self._extract_output_content(result)
            response_metadata = self._extract_response_metadata(result)

            # Process billing
            await process_billing(
                user_id=user_id,
                model_name=self.model_name,
                input_content=input_content,
                output_content=output_content,
                response_metadata=response_metadata,
                request_id=request_id,
            )

            return result

        except Exception as e:
            # Log failed usage (no billing)
            await log_failed_usage(
                user_id=user_id,
                model_name=self.model_name,
                request_id=request_id,
                error_message=str(e),
            )
            raise

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        """Sync invoke - not recommended, use ainvoke"""
        raise NotImplementedError(
            "Synchronous invoke not supported for billing proxy. "
            "Use ainvoke instead."
        )

    async def astream(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        """Async streaming with billing

        Note: Billing is processed after the full stream completes
        """
        # Pre-request checks
        user_id = await self._pre_request_checks()
        request_id = str(uuid.uuid4())

        # Extract input for token counting
        input_content = self._extract_input_content(*args, **kwargs)

        # Collect streaming output
        output_chunks = []
        response_metadata = None

        try:
            async for chunk in self.base_llm.astream(*args, **kwargs):
                output_chunks.append(chunk)

                # Extract metadata from final chunk if available
                if hasattr(chunk, "response_metadata"):
                    response_metadata = chunk.response_metadata

                yield chunk

            # Combine output content
            output_content = self._combine_stream_chunks(output_chunks)

            # Process billing after streaming completes
            await process_billing(
                user_id=user_id,
                model_name=self.model_name,
                input_content=input_content,
                output_content=output_content,
                response_metadata=response_metadata,
                request_id=request_id,
            )

        except Exception as e:
            # Log failed usage
            await log_failed_usage(
                user_id=user_id,
                model_name=self.model_name,
                request_id=request_id,
                error_message=str(e),
            )
            raise

    def _combine_stream_chunks(self, chunks: list[Any]) -> str:
        """Combine streaming chunks into output content

        Args:
            chunks: List of streaming chunks

        Returns:
            Combined output content
        """
        content_parts = []
        for chunk in chunks:
            if hasattr(chunk, "content") and chunk.content:
                content_parts.append(str(chunk.content))
            else:
                content_parts.append(str(chunk))

        return "".join(content_parts)

    def __getattr__(self, name: str) -> Any:
        """Delegate other attributes to base LLM"""
        return getattr(self.base_llm, name)
