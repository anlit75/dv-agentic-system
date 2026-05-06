import { tool } from "@opencode-ai/plugin"
import path from "path"

export default tool({
  description:
    "Generate a structured markdown report from the aggregated results of a verification " +
    "session. Sections include Summary, Simulation Results, Coverage, Issues Found, and " +
    "Recommended Next Steps. " +
    "Use at the end of any workflow to produce a human-readable summary for PR review " +
    "or ticket creation. " +
    "Returns the full markdown report text and writes it to output_path if specified.",
  args: {
    session_results: tool.schema
      .string()
      .describe(
        "Concatenated output from all agents in the session. " +
        "Label each block with the agent name, e.g. '### SimController\\n...\\n### LogAnalyzer\\n...'."
      ),
    output_path: tool.schema
      .string()
      .default("")
      .describe(
        "Where to write the report, relative to worktree root. " +
        "Supports {task_id} placeholder. Leave empty to skip writing."
      ),
  },
  async execute(args, context) {
    const script = path.join(import.meta.dir, "_run_agent.sh")

    const tmpFile = path.join(import.meta.dir, `.tmp_report_${Date.now()}.txt`)
    await Bun.write(tmpFile, args.session_results)

    const extraArgs: string[] = []
    if (args.output_path.trim()) {
      extraArgs.push("--output-path", args.output_path)
    }

    try {
      const result = await Bun.$`bash ${script} reporter
        --input-file ${tmpFile}
        ${extraArgs}`.text()
      return result.trim()
    } finally {
      await Bun.$`rm -f ${tmpFile}`.quiet()
    }
  },
})
