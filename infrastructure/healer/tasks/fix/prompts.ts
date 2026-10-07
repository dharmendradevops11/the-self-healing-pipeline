import { InvestigationReport, EnrichedHealerEvent } from "../../lambdas/shared/types";

/**
 * Strips prompt-injection patterns from untrusted Sentry/user data
 * before embedding in Bedrock prompts.
 */
const sanitizeForPrompt = (text: string): string => {
  return text
    .replace(/```/g, "'''") // Break code fences attackers use to escape context
    .replace(/\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b/gi, "[REDACTED]")
    .replace(/\byou\s+(?:are|must|should|will)\s+now\b/gi, "[REDACTED]")
    .slice(0, 2000); // Hard cap on user-controlled text length
};

export const FIX_SYSTEM_PROMPT = `You are an expert software engineer generating a minimal code fix for a production issue in a TypeScript/Node.js backend.

RULES:
- Respond with ONLY valid JSON in a \`\`\`json code block.
- The diff field must be valid unified diff (git diff format).
- Scope changes ONLY to files listed in affectedFiles.
- NEVER modify existing migration files, .github/, .husky/, CI configs.
- NEVER modify files in: infrastructure/, .github/, .husky/, migrations/ (existing files), Dockerfile*, *.yaml, *.sh, *.json at repo root.
- Only modify files under the safe path prefixes defined in validateAffectedFiles() in the fix runner.
- If confidence < 60 or you cannot produce a safe fix, set type to "investigation-only".
- Keep explanation under 400 characters.

Response schema:
\`\`\`json
{
  "type": "code-fix",
  "diff": "string (unified diff)",
  "affectedFiles": ["relative/path/to/file.ts"],
  "explanation": "string (max 400 chars)",
  "confidenceScore": 0
}
\`\`\``;

export const buildFixPrompt = (
  event: EnrichedHealerEvent,
  investigation: InvestigationReport,
  fileContents: Record<string, string>,
): string => {
  const fileDump = Object.entries(fileContents)
    .map(([p, content]) => `### ${p}\n\`\`\`typescript\n${content.slice(0, 4000)}\n\`\`\``)
    .join("\n\n");

  return `## Issue to Fix
${sanitizeForPrompt(event.title)}
Service: ${event.affectedService}

## Investigation
Root cause: ${sanitizeForPrompt(investigation.rootCauseHypothesis)}
Confidence: ${investigation.confidenceScore}/100
Fix strategy: ${investigation.fixStrategy}
Files to modify: ${investigation.affectedFiles.join(", ")}

## Current File Contents
${fileDump}

Produce ${investigation.confidenceScore >= 60 ? "a code fix" : "an investigation-only report (confidence too low)"} and return the JSON response.`;
};
