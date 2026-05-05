import abc
from dataclasses import dataclass
from typing import Literal


@dataclass
class AgentConfig:
    """Configuration for an Agent.

    Attributes:
        name: Unique identifier for the agent.
        budget: Maximum number of iterations allowed.
        environment: Execution context, either "internal" (local) or "external" (remote).
    """

    name: str
    budget: int = 10
    environment: Literal["internal", "external"] = "internal"

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if not self.name:
            raise ValueError("Agent name cannot be empty.")
        if self.budget <= 0:
            raise ValueError(f"Agent budget must be positive, got {self.budget}.")
        if self.environment not in ("internal", "external"):
            raise ValueError(f"Invalid environment: {self.environment}")


class BaseAgent(abc.ABC):
    """Abstract base class for all Agents in the UVM system."""

    def __init__(self, config: AgentConfig):
        """Initialize the agent with a configuration."""
        if not isinstance(config, AgentConfig):
            raise TypeError("config must be an instance of AgentConfig")
        self.config = config
        self.iteration = 0

    @abc.abstractmethod
    async def run(self, task_input: str) -> str:
        """Execute the agent's core logic.

        Args:
            task_input: The input string describing the task.

        Returns:
            A string representing the result or next steps.
        """

    async def check_budget(self) -> bool:
        """Check if the agent still has remaining budget to continue iterations.

        Note: Subclasses should prefer calling ``step()`` which both checks
        the budget and increments the iteration counter.
        """
        if self.iteration < 0:
            raise RuntimeError(f"Invalid iteration state: {self.iteration}")
        return self.iteration < self.config.budget

    async def step(self) -> bool:
        """Advance agent by one iteration.

        Returns:
            True if budget remains, False otherwise.
        """
        if await self.check_budget():
            self.iteration += 1
            return True
        return False
