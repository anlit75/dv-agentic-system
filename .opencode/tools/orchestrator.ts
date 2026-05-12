/* LICENSE HEADER MANAGED BY add-license-header
 *
 * SPDX-FileCopyrightText: 2026 Ting-An Cheng
 * SPDX-License-Identifier: MIT
 */

import { tool } from "@opencode-ai/plugin"
import path from "path"

export default tool({
  description:
    "Route a verification task through the full agent pipeline (Workflows 1, 2, or 3). " +
    "Automatically dispatches to spec_analyst, code_generator, sim_controller, " +
    "log_analyzer, coverage_analyst, bug_classifier, and reporter as needed. " +
    "Use this as the primary entry point for complex tasks that span multiple agents, " +
    "such as 'develop verification for X feature' or 'regression has 5 fails, analyse'. " +
    "Returns an Orchestrator Result with workflow, final status, and steps taken.",
  args: {
    task: tool.schema
      .string()
      .describe(
        "Free-form task description. Include any relevant context such as failing test names, " +
        "coverage percentages, or spec document text."
      ),
    simulator: tool.schema
      .enum(["xcelium", "ghdl", "icarus", "verilator"])
      .default("xcelium")
      .describe("Simulator adapter for the SimController sub-agent."),
    adapter: tool.schema
      .enum(["imc", "pyuvm"])
      .default("imc")
      .describe("Coverage adapter for the CoverageAnalyst sub-agent."),
    budget: tool.schema
      .number()
      .default(10)
      .describe("Maximum orchestration cycles (default: 10)."),
    sub_budget: tool.schema
      .number()
      .default(5)
      .describe("Budget for each sub-agent (default: 5)."),
    coverage_threshold: tool.schema
      .number()
      .default(90.0)
      .describe("Coverage threshold forwarded to CoverageAnalyst (default: 90.0)."),
    confidence_threshold: tool.schema
      .number()
      .default(0.75)
      .describe("Confidence threshold forwarded to BugClassifier (default: 0.75)."),
  },
  async execute(args, context) {
    const script = path.join(import.meta.dir, "_run_agent.sh")

    const tmpFile = path.join(import.meta.dir, `.tmp_orch_${Date.now()}.txt`)
    await Bun.write(tmpFile, args.task)

    try {
      const result = await Bun.$`bash ${script} orchestrator
        --input-file          ${tmpFile}
        --simulator           ${args.simulator}
        --adapter             ${args.adapter}
        --budget              ${String(args.budget)}
        --sub-budget          ${String(args.sub_budget)}
        --coverage-threshold  ${String(args.coverage_threshold)}
        --confidence-threshold ${String(args.confidence_threshold)}`.text()
      return result.trim()
    } finally {
      await Bun.$`rm -f ${tmpFile}`.quiet()
    }
  },
})
