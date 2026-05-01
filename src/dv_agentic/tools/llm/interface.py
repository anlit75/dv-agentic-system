import abc


class BaseLLMClient(abc.ABC):
    """Abstract base class for LLM clients."""

    @abc.abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1000,
    ) -> str:
        """Complete the given conversation.

        Args:
            system: The system prompt.
            messages: A list of message dictionaries (e.g., {"role": "user", "content": "..."}).
            max_tokens: The maximum number of tokens to generate.

        Returns:
            The generated response string.
        """
