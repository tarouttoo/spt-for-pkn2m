# Agent CI pipeline (sandcastle)

AFK runs of the pi coding agent in GitHub Actions, one issue per run.
Ported from the welding-ok pipeline.

## Triggers

- **Manual**: Actions → Agent Implement → Run workflow → issue number.
- **Automatic**: label an issue with `ready-for-agent`.

## What a run does

1. Builds the sandbox image (`.sandcastle/Containerfile`: node 24 + gh +
   python3 + uv for the cadgen checks).
2. Runs pi (GLM via z.ai) in a rootless Podman sandbox via
   `.sandcastle/main.ts` with `.sandcastle/prompt.md`.
3. Pushes `agent/issue-<N>` and opens a PR against `master`; the workflow
   appends `Closes #<N>` to the agent-drafted body.
4. The agent leaves its report as a comment on the issue.

The human reviews/merges the PR; the merge closes the issue.

## Prerequisites

- Repo secret `ZAI_API_KEY` (z.ai coding API key).
- `package-lock.json` committed (`npm ci` in the workflow).
- If issues need the normative documents, `reference/` must be tracked in git
  (~54 MB, largest file 43 MB — fits GitHub without LFS).

## Local run

```sh
npm install
podman build -t sandcastle:spt-for-pkn2m -f .sandcastle/Containerfile .sandcastle
ZAI_API_KEY=... GH_TOKEN=$(gh auth token) GH_REPO=<owner>/<repo> npx tsx .sandcastle/main.ts 42
```
