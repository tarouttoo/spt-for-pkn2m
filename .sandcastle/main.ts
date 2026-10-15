import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname } from "node:path";
import { run, pi } from "@ai-hero/sandcastle";
import { podman } from "@ai-hero/sandcastle/sandboxes/podman";

// Issue-driven AFK run: implement one local-markdown issue from
// .scratch/<feature>/issues/ on its own branch.
// Usage: npx tsx .sandcastle/main.ts .scratch/spt-tank/issues/05-foo.md
//        ISSUE_PATH=.scratch/... npx tsx .sandcastle/main.ts

const issuePath = process.argv[2] ?? process.env.ISSUE_PATH;
const validPath =
  issuePath &&
  /^\.scratch\/[^/]+\/issues\/[^/]+\.md$/.test(issuePath) &&
  existsSync(issuePath);
if (!validPath) {
  console.error(
    "Usage: npx tsx .sandcastle/main.ts .scratch/<feature>/issues/<NN>-<slug>.md",
  );
  process.exit(1);
}

const slug = basename(issuePath, ".md");
const feature = basename(dirname(dirname(issuePath)));
const branch = `agent/${feature}/${slug}`;

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

// Explicit allowlist: only these variables enter the container. Issues are
// local markdown files, so the sandboxed agent needs no gh/GitHub token.
const sandboxEnv = {
  ZAI_API_KEY: requiredEnvVar("ZAI_API_KEY"),
};

const result = await run({
  name: `implement-${slug}`,
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
  promptArgs: { ISSUE_PATH: issuePath, BRANCH: branch },
  maxIterations: 3,
});

console.log(`\nDone. branch=${result.branch} commits=${result.commits.length}`);
for (const c of result.commits) console.log(`  ${c.sha}`);
