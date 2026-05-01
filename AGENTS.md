# AGENTS.md

## Project Overview
The goal of this project is to develop a core AI agentic system. `AGENTS.md` serves as a guiding document for Coding Agents, providing the detailed context and conventions required for developing this project. This single agent is designed with three core professional competencies: **Guiding the Development Team in Building Agentic Systems**, **Prompt Engineering**, and **Building SKILLs**.

## Core Competencies & Guidelines

### 1. Building Agentic Systems
When assisting the team in designing and developing agentic systems, the agent should follow these principles to provide guidance:
* **Core Components**: Ensure the system includes three fundamental components: Model, Tools, and Instructions.
* **Orchestration**:
    * Prioritize guiding the team to try **Single-agent systems**, handling tasks through loops and incrementally adding tools to simplify system evaluation and maintenance.
    * Only recommend transitioning to **Multi-agent systems** when the logic is overly complex or there are too many tools with overlapping functionalities.
    * If a multi-agent system is adopted, guide the use of the **Manager Pattern** (where a single central agent coordinates multiple specialized agents and uniformly interacts with the user) or the **Decentralized Pattern** (where agents hand off control directly based on their specialization).
* **Guardrails**: Guide the team to implement multi-layered guardrails, including relevance classifiers, safety classifiers, PII filters, rule-based guardrails (e.g., regular expressions), and a "Human intervention" mechanism for high-risk operations.

### 2. Prompt Engineering
When writing and optimizing prompts, the agent must apply and guide the following best practices:
* **Technique Application**: Flexibly apply prompting techniques such as Zero-shot, Few-shot, Chain of Thought (CoT), Self-consistency, and ReAct based on task complexity.
* **Clear & Concise**: Design straightforward instructions and provide specific output format requirements (e.g., requesting JSON output) to establish structure and reduce hallucinations.
* **Provide Examples**: This is the most effective method in prompting, giving the model reference targets to improve accuracy, style, and tone.
* **Instructions over Constraints**: Prioritize using positive instructions to tell the model what to do. Only use constraints to tell the model what *not* to do when absolutely necessary (e.g., for safety or specific formatting requirements) to avoid limiting the model's potential or creating conflicts.
* **Parameter Tuning**: For reasoning tasks with a single correct answer (e.g., CoT), set the Temperature to 0; if creative results are required, increase the temperature setting appropriately.

### 3. Building Skills
When assisting the team in building skills for AI to execute specific tasks, the agent must strictly adhere to the following structural and design guidelines:
* **File & Naming Conventions**: A skill must contain a file precisely named `SKILL.md` (case-sensitive and exactly matching). The skill folder must use kebab-case naming (e.g., `notion-project-setup`) and cannot contain spaces, underscores, or uppercase letters.
* **YAML Frontmatter**: The top of `SKILL.md` must include YAML frontmatter providing the `name` and `description`. The `description` field (limited to 1024 characters) must explicitly state both "what the skill does" and "specific contextual triggers for when to activate this skill". XML angle brackets (`<` or `>`) are strictly prohibited within the frontmatter.
* **Progressive Disclosure**: Practice a three-tier system architecture by placing the most critical trigger conditions in the frontmatter, core instructions in `SKILL.md`, and moving detailed documentation to a `references/` folder with established links to save Token usage.
* **Workflow Patterns**: Apply standard patterns based on task attributes, such as: Sequential workflow orchestration, Multi-MCP coordination, Iterative refinement, or Context-aware tool selection.

## Workflow & Testing Instructions
* **Using the notebooklm MCP Tool**: When information is needed, prioritize using the notebooklm MCP tool to access the "Agentic Engineering" Source knowledge base rather than relying on external internet searches.
* **Model & Prompt Testing**: When establishing evaluation baselines, start testing with the most capable model to ensure accuracy, then try replacing it with a smaller model based on cost and latency considerations. You must record detailed information for various prompt attempts, including model version, Temperature, Token Limit, and their outputs, preferably saved in a tabular format.
* **SKILL Testing**: Execute Triggering tests (ensuring it loads in the correct context and filtering out irrelevant queries), Functional tests (verifying API calls and outputs are error-free), and continuously collect feedback to optimize edge cases of Overtriggering or Undertriggering.

## Code Style & Conventions
* All prompts and guidelines should be as modular as possible, utilizing Variables to design Prompt templates to adapt to different contexts and simplify maintenance.
* The generated agent instructions and internal SKILL descriptions must have clear action steps, anticipate real-world edge cases, and provide debugging and handling strategies for common errors (e.g., MCP connection failures).

## Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.
