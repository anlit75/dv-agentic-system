/* LICENSE HEADER MANAGED BY add-license-header
 *
 * SPDX-FileCopyrightText: 2026 Ting-An Cheng
 * SPDX-License-Identifier: MIT
 */

/**
 * @deprecated (dv-agentic v2+)
 * CoverageAnalystService now handles threshold comparison directly inside
 * OrchestratorAgent.  LLM-powered hole analysis (Workflow 3) still routes
 * through `run_coverage_analyst` in the Orchestrator.
 * Prefer calling `run_orchestrator` instead of invoking this tool directly.
 * This wrapper is retained for backward compatibility with existing installations.
 */
import { tool } from "@opencode-ai/plugin"
import path from "path"

export default tool({
  description:
    "Retrieve overall functional coverage for a simulation job and report " +
    "whether it meets the threshold. " +
    "Use after a simulation run completes when you need to know the coverage " +
    "percentage before deciding on next steps. " +
    "Returns a Coverage Summary including status (OK / BELOW THRESHOLD) and gap.",
  args: {
    job_id: tool.schema
      .string()
      .describe("Simulation job identifier, e.g. 'axi_burst_test_42'."),
    adapter: tool.schema
      .enum(["imc", "pyuvm"])
      .default("imc")
      .describe("Coverage tool adapter. Use 'imc' for Xcelium/IMC (internal), 'pyuvm' for GHDL/cocotb (external)."),
    threshold: tool.schema
      .number()
      .default(90.0)
      .describe("Minimum acceptable coverage percentage (default: 90.0)."),
  },
  async execute(args, context) {
    const script = path.join(import.meta.dir, "_run_agent.sh")
    const result = await Bun.$`bash ${script} coverage_analyst
      --job-id   ${args.job_id}
      --adapter  ${args.adapter}
      --threshold ${String(args.threshold)}`.text()
    return result.trim()
  },
})
