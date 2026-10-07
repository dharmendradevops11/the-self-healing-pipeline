import { spawnSync, SpawnSyncOptions } from "child_process";

export interface SpawnResult {
  stdout: string;
  stderr: string;
  status: number;
}

/**
 * Runs a command with array arguments (shell:false — no injection risk).
 * Throws if process exits non-zero and throwOnError is true (default).
 */
export const safeSpawn = (
  command: string,
  args: string[],
  options: SpawnSyncOptions & { throwOnError?: boolean } = {},
): SpawnResult => {
  const { throwOnError = true, ...spawnOpts } = options;
  const result = spawnSync(command, args, { shell: false, ...spawnOpts });
  const stdout = result.stdout?.toString() ?? "";
  const stderr = result.stderr?.toString() ?? "";
  const status = result.status ?? 1;

  if (throwOnError && status !== 0) {
    throw new Error(`Command ${command} ${args.join(" ")} exited ${status}:\n${stderr}`);
  }

  return { stdout, stderr, status };
};
