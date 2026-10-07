import simpleGit, { SimpleGit } from "simple-git";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import { safeSpawn } from "./spawn";

export interface CloneResult {
  repoPath: string;
  git: SimpleGit;
}

export const cloneRepo = async (): Promise<CloneResult> => {
  const repoUrl = process.env.GITHUB_REPO_URL ?? "https://github.com/YOUR-GITHUB-ORG/your-repo.git";
  const token = process.env.GITHUB_TOKEN ?? "";
  const branch = process.env.GITHUB_BASE_BRANCH ?? "develop";

  const authenticatedUrl = token
    ? repoUrl.replace("https://", `https://x-access-token:${token}@`)
    : repoUrl;

  const repoPath = path.join(os.tmpdir(), `healer-${Date.now()}`);
  fs.mkdirSync(repoPath, { recursive: true });

  const git = simpleGit();
  await git.clone(authenticatedUrl, repoPath, ["--depth", "1", "--branch", branch]);

  const repoGit = simpleGit(repoPath);
  await repoGit.addConfig("user.email", "healer@your-domain.com");
  await repoGit.addConfig("user.name", "AI Self-Healer");

  return { repoPath, git: repoGit };
};

export const applyPatch = (repoPath: string, diff: string): void => {
  const patchPath = path.join(os.tmpdir(), `healer-patch-${Date.now()}.patch`);
  fs.writeFileSync(patchPath, diff, "utf8");
  try {
    // --3way: falls back to 3-way merge on context drift (more forgiving)
    // --whitespace=fix: auto-correct CRLF/trailing-space mismatches
    safeSpawn("git", ["apply", "--3way", "--whitespace=fix", patchPath], { cwd: repoPath });
  } finally {
    fs.unlinkSync(patchPath);
  }
};

export const readFileFromRepo = (repoPath: string, filePath: string): string => {
  const fullPath = path.resolve(repoPath, filePath);
  // Reject path traversal — resolved path must stay within the repo root.
  if (!fullPath.startsWith(path.resolve(repoPath) + path.sep)) return "";
  if (!fs.existsSync(fullPath)) return "";
  return fs.readFileSync(fullPath, "utf8");
};

export const getRecentCommitsForFiles = async (
  git: SimpleGit,
  files: string[],
  count = 5,
): Promise<string> => {
  if (files.length === 0) return "";
  const log = await git.log({ maxCount: count, file: files[0] });
  return log.all.map((c) => `${c.hash.slice(0, 8)} ${c.date} ${c.message}`).join("\n");
};

export const createBranchAndPush = async (
  git: SimpleGit,
  branchName: string,
  commitMessage: string,
  filePaths: string[],
): Promise<void> => {
  await git.checkoutLocalBranch(branchName);
  await git.add(filePaths);
  await git.commit(commitMessage);
  await git.push("origin", branchName, ["--set-upstream"]);
};

// Writes a brand-new file to the repo and commits it — used when the pipeline
// produces an investigation-only report (no code diff to apply).
export const createBranchWithNewFile = async (
  git: SimpleGit,
  repoPath: string,
  branchName: string,
  filePath: string,
  fileContent: string,
  commitMessage: string,
): Promise<void> => {
  await git.checkoutLocalBranch(branchName);
  const fullPath = path.join(repoPath, filePath);
  fs.mkdirSync(path.dirname(fullPath), { recursive: true });
  fs.writeFileSync(fullPath, fileContent, "utf8");
  await git.add(filePath);
  await git.commit(commitMessage);
  await git.push("origin", branchName, ["--set-upstream"]);
};
