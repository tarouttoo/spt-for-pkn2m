# Agent CI pipeline (sandcastle)

AFK runs of the pi coding agent in GitHub Actions, one issue file per run.
Ported from the welding-ok pipeline; adapted to this repo's local-markdown
issue tracker.

## Triggers

- **Manual**: Actions → Agent Implement → Run workflow → `issue_path`
  (e.g. `.scratch/spt-tank/issues/05-geometriya-i-tolshchina-stenki.md`).
- **Automatic**: push to `master` touching `.scratch/*/issues/*.md`, where the
  new content of a changed file carries `Status: ready-for-agent`. First match
  per push is implemented; the rest wait for the next run.

## What a run does

1. Validates the issue file is `Status: ready-for-agent`.
2. Builds the sandbox image (`.sandcastle/Containerfile`: node 24 + python3 +
   uv for the cadgen checks; no gh — issues are local files).
3. Runs pi (GLM via z.ai) in a rootless Podman sandbox via
   `.sandcastle/main.ts` with `.sandcastle/prompt.md`.
4. Pushes `agent/<feature>/<NN>-<slug>` and opens a PR against `master`.
5. The agent itself, on the branch: sets the issue to
   `Status: ready-for-human` (implementation done, awaiting human review) and
   appends its report under `## Comments` in the issue file.

The human reviews/merges the PR and then sets the issue to `resolved`
themselves.

## Prerequisites

- Repo secret `ZAI_API_KEY` (z.ai coding API key).
- `package-lock.json` committed (`npm ci` in the workflow).
- If issues need the normative documents, `reference/` must be tracked in git
  (~54 MB, largest file 43 MB — fits GitHub without LFS). It is currently
  untracked; until it is, the sandboxed agent works only from the committed
  `research/` summaries.

## Local run

```sh
npm install
podman build -t sandcastle:spt-for-pkn2m -f .sandcastle/Containerfile .sandcastle
ZAI_API_KEY=... npx tsx .sandcastle/main.ts .scratch/spt-tank/issues/05-geometriya-i-tolshchina-stenki.md
```
