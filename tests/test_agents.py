"""Unit tests for the base agent and budget management."""

import pytest

from dv_agentic.agents.base import AgentConfig, BaseAgent


class MockAgent(BaseAgent):
    """A mock agent for testing budget management."""

    async def run(self, task_input: str) -> str:
        return f"Processed: {task_input}"


@pytest.mark.asyncio
async def test_agent_budget_management() -> None:
    config = AgentConfig(name="test_agent", budget=2)
    agent = MockAgent(config)

    assert agent.iteration == 0
    assert await agent.check_budget() is True

    # First step
    assert await agent.step() is True
    assert agent.iteration == 1
    assert await agent.check_budget() is True

    # Second step
    assert await agent.step() is True
    assert agent.iteration == 2
    assert await agent.check_budget() is False  # Budget exhausted

    # Third step (fails)
    assert await agent.step() is False
    assert agent.iteration == 2
