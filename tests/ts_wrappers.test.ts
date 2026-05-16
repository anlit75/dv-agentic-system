/* LICENSE HEADER MANAGED BY add-license-header
 *
 * SPDX-FileCopyrightText: 2026 Ting-An Cheng
 * SPDX-License-Identifier: MIT
 */

import { describe, expect, test, mock, beforeEach, afterEach } from "bun:test";
import * as path from "path";

// Mock the @opencode-ai/plugin to just return the config object
const dummySchema = {
  string: () => dummySchema,
  number: () => dummySchema,
  boolean: () => dummySchema,
  enum: () => dummySchema,
  default: () => dummySchema,
  describe: () => dummySchema,
};

const toolMock = (config: any) => config;
toolMock.schema = dummySchema;

mock.module("@opencode-ai/plugin", () => ({
  tool: toolMock
}));

const tools = [
  "bug_classifier.ts",
  "code_generator.ts",
  "coverage_analyst.ts",
  "log_analyzer.ts",
  "orchestrator.ts",
  "reporter.ts",
  "sim_controller.ts",
  "spec_analyst.ts"
];

describe("OpenCode Tools Wrappers Execute Function", () => {
  let bunDollarMock: any;
  let bunWriteMock: any;

  beforeEach(() => {
    // Setup global Bun mocks
    bunWriteMock = mock(() => Promise.resolve());
    globalThis.Bun.write = bunWriteMock;

    bunDollarMock = mock(() => {
      return {
        text: () => Promise.resolve("mocked_output"),
        quiet: () => Promise.resolve()
      };
    });
    // @ts-ignore
    globalThis.Bun.$ = bunDollarMock;
  });

  afterEach(() => {
    mock.restore();
  });

  for (const tool of tools) {
    test(`${tool} execute() should construct CLI commands without failing`, async () => {
      const toolPath = path.join(import.meta.dir, "..", "tools", tool);
      const module = await import(toolPath);

      const config = module.default;
      expect(config.execute).toBeDefined();

      const fakeArgs = {
        task_id: "test",
        description: "test",
        budget: 5,
        test: "test",
        seed: 1,
        simulator: "test",
        top: "test",
        debug: false,
        job_id: "test",
        adapter: "test",
        threshold: 90,
        input_file: "test",
        output_path: "",
        file_list: "",
        base_branch: "test"
      };

      const fakeContext = {};

      await config.execute(fakeArgs, fakeContext);

      // Verify Bun.$ was called to execute the python CLI
      expect(bunDollarMock).toHaveBeenCalled();
    });
  }
});
