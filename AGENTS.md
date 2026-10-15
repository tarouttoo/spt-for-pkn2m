## Agent skills

### Issue tracker

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) map 1:1 to their default label strings. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Agent CI pipeline

AFK agent runs in GitHub Actions, one issue per run: label an issue `ready-for-agent`, or dispatch the `Agent Implement` workflow manually with an issue number. See `docs/agents/ci.md`.
