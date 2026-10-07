import { EnrichedHealerEvent } from "../../lambdas/shared/types";

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

export const INVESTIGATION_SYSTEM_PROMPT = `You are an expert software engineer performing root cause analysis on a production issue in a TypeScript/Node.js backend. Adapt your analysis to the actual stack visible in the files you read.

Analyse the error context and produce a structured JSON investigation report.

RULES:
- Respond with ONLY valid JSON inside a \`\`\`json code block.
- Confidence score 0-100: 90+ = single clear cause. 60-89 = likely cause. 30-59 = hypothesis only. <30 = insufficient context.
- affectedFiles must be actual file paths from the stack trace — not guesses.
- Keep rootCauseHypothesis under 300 characters.

Response schema:
\`\`\`json
{
  "rootCauseHypothesis": "string (max 300 chars)",
  "confidenceScore": 0,
  "affectedFiles": ["relative/path/to/file.ts"],
  "fixStrategy": "string (max 500 chars)"
}
\`\`\``;

export const buildInvestigationPrompt = (
  event: EnrichedHealerEvent,
  fileContents: Record<string, string>,
  recentCommits: string,
): string => {
  const logSample = event.cloudwatchLogs
    .slice(-20)
    .map((l) => sanitizeForPrompt(l.message).slice(0, 500))
    .join("\n");
  const fileDump = Object.entries(fileContents)
    .map(([p, content]) => `### ${p}\n\`\`\`typescript\n${content.slice(0, 3000)}\n\`\`\``)
    .join("\n\n");

  return `## Issue
Title: ${sanitizeForPrompt(event.title)}
Severity: ${event.severity} | Service: ${event.affectedService}
${event.sentryIssueUrl ? `Sentry: ${event.sentryIssueUrl}` : ""}
${event.sentryEventCount ? `Occurrence count: ${event.sentryEventCount}` : ""}

## Stack Trace
${event.stackTrace ? sanitizeForPrompt(event.stackTrace) : "Not available"}

## Recent CloudWatch Logs
${logSample || "No logs available"}

## Source Files
${fileDump || "No source files extracted"}

## Recent Commits
${recentCommits || "Not available"}

Return the JSON investigation report.`;
};
