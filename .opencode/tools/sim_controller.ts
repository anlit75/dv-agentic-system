import { tool } from "@opencode-ai/plugin"
import path from "path"

export default tool({
  description:
    "Compile source files and run a simulation test inside a dedicated git branch " +
    "(agent/{task_id}). Retries up to 'budget' times on failure. " +
    "Use this whenever you need to run a simulation and track results on a branch " +
    "ready for PR review. " +
    "Returns a Task Complete report with final status and branch name.",
  args: {
    task_id: tool.schema
      .string()
      .describe("Unique task identifier — also used as the git branch suffix."),
    test: tool.schema
      .string()
      .describe("UVM test name or cocotb test module (e.g. 'axi_burst_test')."),
    seed: tool.schema
      .number()
      .describe("Random seed for the simulation run."),
    simulator: tool.schema
      .enum(["xcelium", "ghdl", "icarus", "verilator"])
      .default("xcelium")
      .describe("Simulator adapter to use."),
    top: tool.schema
      .string()
      .default("top")
      .describe("Top-level HDL module name."),
    debug: tool.schema
      .boolean()
      .default(false)
      .describe("Enable debug mode (waveform dumping)."),
    budget: tool.schema
      .number()
      .default(10)
      .describe("Maximum number of simulation retries."),
    base_branch: tool.schema
      .string()
      .default("main")
      .describe("Git branch to fork from."),
    file_list: tool.schema
      .string()
      .default("")
      .describe("Space-separated list of source files to compile. Leave empty if project is pre-compiled."),
  },
  async execute(args, context) {
    const script = path.join(import.meta.dir, "_run_agent.sh")

    const baseArgs = [
      "sim_controller",
      "--task-id",    args.task_id,
      "--test",       args.test,
      "--seed",       String(args.seed),
      "--simulator",  args.simulator,
      "--top",        args.top,
      "--budget",     String(args.budget),
      "--base-branch", args.base_branch,
    ]

    if (args.debug) baseArgs.push("--debug")
    if (args.file_list.trim()) {
      baseArgs.push("--file-list", ...args.file_list.trim().split(/\s+/))
    }

    const result = await Bun.$`bash ${script} ${baseArgs}`.text()
    return result.trim()
  },
})
