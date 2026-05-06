import { tool } from "@opencode-ai/plugin"
import path from "path"

export default tool({
  description:
    "Generate or modify SystemVerilog / UVM code through a multi-turn LLM dialogue. " +
    "Writes files directly into the current git branch under the worktree. " +
    "Use this when you need new sequences, scoreboards, coverage groups, or bug fixes " +
    "targeting a specific coverage bin or simulation failure. " +
    "Returns a Code Generation Report listing files written and final confidence.",
  args: {
    task_id: tool.schema
      .string()
      .default("codegen_task")
      .describe("Task identifier used in the report and commit messages."),
    description: tool.schema
      .string()
      .describe(
        "Natural-language description of what to generate or fix. " +
        "Include the target bin name, base class constraints, and any VIP rules."
      ),
    budget: tool.schema
      .number()
      .default(5)
      .describe("Maximum LLM iterations before giving up (default: 5)."),
  },
  async execute(args, context) {
    const script = path.join(import.meta.dir, "_run_agent.sh")

    // Write description to a temp file so it survives shell quoting
    const tmpFile = path.join(import.meta.dir, `.tmp_codegen_${Date.now()}.txt`)
    await Bun.write(tmpFile, args.description)

    try {
      const result = await Bun.$`bash ${script} code_generator
        --task-id    ${args.task_id}
        --input-file ${tmpFile}
        --budget     ${String(args.budget)}`.text()
      return result.trim()
    } finally {
      await Bun.$`rm -f ${tmpFile}`.quiet()
    }
  },
})
