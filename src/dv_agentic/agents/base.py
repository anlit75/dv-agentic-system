import abc
from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Configuration for an Agent."""

    name: str
    budget: int = 10
    environment: str = "internal"


class BaseAgent(abc.ABC):
    """Abstract base class for all Agents in the UVM system."""

    def __init__(self, config: AgentConfig):
        """Initialize the agent with a configuration."""
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

    def check_budget(self) -> bool:
        """Check if the agent still has remaining budget to continue iterations."""
        return self.iteration < self.config.budget
