/* LICENSE HEADER MANAGED BY add-license-header
 *
 * SPDX-FileCopyrightText: 2026 Ting-An Cheng
 * SPDX-License-Identifier: MIT
 */

import { tool } from "@opencode-ai/plugin"
import path from "path"

export default tool({
  description:
    "Parse a hardware specification document and generate a structured verification plan " +
    "(vplan.yaml) listing features, priorities, and coverage bins. " +
    "Use at the start of Workflow 1 when you receive a new spec and need to plan " +
    "what to verify before writing any testbench code. " +
    "Returns a Vplan Result with feature count and the path where vplan.yaml was written.",
  args: {
    spec_text: tool.schema
      .string()
      .describe(
        "Full text of the specification document. For PDFs, extract the text first " +
        "and pass it here as a plain string."
      ),
    output_path: tool.schema
      .string()
      .default(".agent/vplan.yaml")
      .describe("Where to write the vplan, relative to the worktree root."),
    budget: tool.schema
      .number()
      .default(5)
      .describe("Maximum LLM iterations (default: 5)."),
  },
  async execute(args, context) {
    const script = path.join(import.meta.dir, "_run_agent.sh")

    const tmpFile = path.join(import.meta.dir, `.tmp_spec_${Date.now()}.txt`)
    await Bun.write(tmpFile, args.spec_text)

    try {
      const result = await Bun.$`bash ${script} spec_analyst
        --input-file  ${tmpFile}
        --output-path ${args.output_path}
        --budget      ${String(args.budget)}`.text()
      return result.trim()
    } finally {
      await Bun.$`rm -f ${tmpFile}`.quiet()
    }
  },
})
