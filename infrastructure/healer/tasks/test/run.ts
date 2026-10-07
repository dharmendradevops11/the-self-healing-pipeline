import * as path from "path";
import * as fs from "fs";
import { cloneRepo } from "../shared/git-client";
import { safeSpawn } from "../shared/spawn";
import { writePipelineState, readPipelineState } from "../shared/s3-client";
import { PipelineState, TestResults, TestCheckResult } from "../../lambdas/shared/types";

const runCheck = (cmd: string, args: string[], cwd: string): TestCheckResult => {
  const result = safeSpawn(cmd, args, { cwd, throwOnError: false, timeout: 300_000 });
  return { passed: result.status === 0, output: (result.stdout + result.stderr).slice(-2000) };
};

const main = async () => {
  const executionId = process.env.EXECUTION_ID;
  if (!executionId) throw new Error("EXECUTION_ID env var required");

  const state = await readPipelineState<PipelineState>(executionId);
  const branchName = state.branchName; // Read from state, not process.env (fixes C7)

  if (!branchName || state.fix?.type !== "code-fix") {
    const skip: TestCheckResult = { passed: true, output: "Skipped — no code fix to test" };
    const updated: PipelineState = {
      ...state,
      testResults: { typeCheck: skip, unitTests: skip, lint: skip, overallPassed: true },
    };
    await writePipelineState(updated);
    return;
  }

  const { repoPath } = await cloneRepo();
  let testResults!: TestResults;

  try {
  safeSpawn("git", ["fetch", "origin", branchName], { cwd: repoPath });
  safeSpawn("git", ["checkout", branchName], { cwd: repoPath });
  safeSpawn("pnpm", ["install", "--frozen-lockfile"], { cwd: repoPath, timeout: 300_000 });

  const changedFiles = state.fix?.affectedFiles ?? [];
  const apiFilesChanged = changedFiles.some((f) => f.includes("src/") || f.includes("lib/"));

  const typeCheck = apiFilesChanged
    ? runCheck("pnpm", ["type:check"], repoPath)
    : { passed: true, output: "Skipped — no source files changed" };

  const fileBasenames = [...new Set(changedFiles.map((f) => path.basename(f, path.extname(f))))];
  const testPattern = fileBasenames.map((n) => `${n}\\.test`).join("|");
  const unitTests = apiFilesChanged
    ? runCheck(
        "pnpm",
        [
          "--filter",
          "YOUR_WORKSPACE", // TODO: replace with your pnpm workspace package name (e.g. "@myorg/api")
          "test:unit",
          "--",
          `--testPathPattern=${testPattern}`,
          "--passWithNoTests",
        ],
        repoPath,
      )
    : { passed: true, output: "Skipped — no API files changed" };

  const tsxFiles = changedFiles.filter((f) => f.endsWith(".ts") || f.endsWith(".tsx"));
  const lint =
    tsxFiles.length > 0
      ? runCheck("npx", ["eslint", "--max-warnings=0", ...tsxFiles], repoPath)
      : { passed: true, output: "Skipped — no TS files changed" };

  testResults = {
    typeCheck,
    unitTests,
    lint,
    overallPassed: typeCheck.passed && unitTests.passed && lint.passed,
  };

  } finally {
    fs.rmSync(repoPath, { recursive: true, force: true });
  }

  const updated: PipelineState = { ...state, testResults };
  await writePipelineState(updated);
  console.log(`[TEST] State written to S3 for execution ${executionId}`);
};

main().catch((err) => {
  console.error("[TEST] Fatal:", err);
  process.exit(1);
});
