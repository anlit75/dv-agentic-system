import { tool } from "@opencode-ai/plugin"
import path from "path"

export default tool({
  description:
    "Classify a simulation failure as TB_BUG (testbench issue) or RTL_BUG (design bug) " +
    "with a confidence score. Flags for human review when confidence is below threshold. " +
    "Use after log analysis when you need to determine whether a fix goes in the " +
    "testbench or requires an RTL ECO. " +
    "Returns a Bug Classification with evidence bullets and a summary.",
  args: {
    failure_summary: tool.schema
      .string()
      .describe(
        "Failure summary text — paste the output of log_analyzer, or any combination of " +
        "log excerpts, spec references, and waveform observations."
      ),
    threshold: tool.schema
      .number()
      .default(0.75)
      .describe("Minimum confidence to accept the classification without human review (default: 0.75)."),
    budget: tool.schema
      .number()
      .default(5)
      .describe("Maximum LLM iterations (default: 5)."),
  },
  async execute(args, context) {
    const script = path.join(import.meta.dir, "_run_agent.sh")

    const tmpFile = path.join(import.meta.dir, `.tmp_bugclf_${Date.now()}.txt`)
    await Bun.write(tmpFile, args.failure_summary)

    try {
      const result = await Bun.$`bash ${script} bug_classifier
        --input-file ${tmpFile}
        --threshold  ${String(args.threshold)}
        --budget     ${String(args.budget)}`.text()
      return result.trim()
    } finally {
      await Bun.$`rm -f ${tmpFile}`.quiet()
    }
  },
})
