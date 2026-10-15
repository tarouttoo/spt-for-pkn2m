## Agent skills

### Issue tracker

Issues and specs for this repo live as markdown files under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) map 1:1 to their default label strings. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Agent CI pipeline

AFK agent runs in GitHub Actions, one issue file per run: set `Status: ready-for-agent` in a `.scratch/<feature>/issues/` file and push, or dispatch the `Agent Implement` workflow manually. See `docs/agents/ci.md`.
