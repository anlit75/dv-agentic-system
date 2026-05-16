/* LICENSE HEADER MANAGED BY add-license-header
 *
 * SPDX-FileCopyrightText: 2026 Ting-An Cheng
 * SPDX-License-Identifier: MIT
 */

/**
 * @deprecated (dv-agentic v2+)
 * LogAnalyzerService is now called automatically by OrchestratorAgent as part
 * of the code → sim → analyze auto-chain after every `run_code_generator` step.
 * Prefer calling `run_orchestrator` instead of invoking this tool directly.
 * This wrapper is retained for backward compatibility with existing installations.
 */
import { tool } from "@opencode-ai/plugin"
import path from "path"

export default tool({
  description:
    "Parse a simulation log file and classify the failure " +
    "(compile_error, uvm_fatal, uvm_error, scoreboard_mismatch, timeout, …). " +
    "Returns a structured Failure Summary with a recommended next step. " +
    "Use this whenever a simulation run produces a log file that needs analysis.",
  args: {
    log_file: tool.schema
      .string()
      .describe("Path to the simulation log file, relative to the project root."),
  },
  async execute(args, context) {
    const script = path.join(import.meta.dir, "_run_agent.sh")
    const result = await Bun.$`bash ${script} log_analyzer --input-file ${args.log_file}`.text()
    return result.trim()
  },
})
