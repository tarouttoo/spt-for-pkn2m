import { homedir } from "node:os";
import { run, pi } from "@ai-hero/sandcastle";
import { podman } from "@ai-hero/sandcastle/sandboxes/podman";

// Issue-driven AFK run: implement one GitHub issue on its own branch.
// Usage: npx tsx .sandcastle/main.ts <issue-number>
//        ISSUE_NUMBER=42 npx tsx .sandcastle/main.ts

const issueNumber = process.argv[2] ?? process.env.ISSUE_NUMBER;
if (!issueNumber || !/^\d+$/.test(issueNumber)) {
  console.error("Usage: npx tsx .sandcastle/main.ts <issue-number>");
  process.exit(1);
}

const branch = `agent/issue-${issueNumber}`;

// Fail the run up front if the sandbox would start without a credential it
// needs — the agent would otherwise fail confusingly mid-task.
function requiredEnvVar(key: string): string {
  const value = process.env[key];
  if (!value) {
    console.error(`Missing required env var: ${key}`);
    process.exit(1);
  }
  return value;
}

// Explicit allowlist: only these variables enter the container.
const sandboxEnv = {
  GH_TOKEN: requiredEnvVar("GH_TOKEN"),
  GH_REPO: requiredEnvVar("GH_REPO"),
  ZAI_API_KEY: requiredEnvVar("ZAI_API_KEY"),
};

const result = await run({
  name: `implement-issue-${issueNumber}`,
  agent: pi("glm-5.3-flash"),
  // Rootless Podman, in every environment. There is no noSandbox fallback on
  // purpose — a broken sandbox must fail the run. The image must be built
  // before the run (sandcastle does not build it) and podman must be on PATH;
  // both fail loudly.
  sandbox: podman({
    env: sandboxEnv,
    // pi's auth/config, provisioned on the host (by CI or interactively),
    // shared read-write into the container home so the sandboxed agent
    // authenticates exactly like the host one.
    mounts: [
      { hostPath: `${homedir()}/.pi/agent`, sandboxPath: "/home/agent/.pi/agent" },
    ],
  }),
  branchStrategy: { type: "branch", branch },
  promptFile: "./.sandcastle/prompt.md",
  promptArgs: { ISSUE_NUMBER: issueNumber, BRANCH: branch },
  maxIterations: 3,
});

console.log(`\nDone. branch=${result.branch} commits=${result.commits.length}`);
for (const c of result.commits) console.log(`  ${c.sha}`);
