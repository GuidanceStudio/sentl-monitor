# CLAUDE.md

This repository is the `sentl-monitor` skill: it designs a monitoring study of what AI
assistants say about a subject, sets it up in Sentl through Sentl's MCP server, and writes a
report after each period of runs. Start every session by reading, in this order:

1. `README.md`: what the skill does, its routes, its requirements.
2. `ARCHITECTURE.md`: the stages, the files each writes, the MCP calls per route, the
   comparison model, and the gaps in Sentl's MCP.
3. `DEVPLAN.md`: the status line at the top, the decisions taken, the milestones.

The status of the work lives in `DEVPLAN.md` only. This file does not repeat it.

## How to work here

- Plan and execute with the `forge-flow` skill, one milestone at a time, test first. While the
  devplan status says "proposed", ask the operator to approve it before starting M1.
- Mark a milestone in progress before writing code and done in the same commit as the work.
- Scripts use the Python standard library only. Tests live under `tests/`. The install script
  follows the other skills of the same author (`./install.sh --force`, `--check`).

## Sentl's MCP server

- Setup page: https://app.sentl.ai/mcp/setup. The tool names depend on the name the server was
  given in the host; read them from the connected server, never hard-code them.
- Read-only tools (lists, project and run reads, the credit estimate) can be called to learn the
  data shapes.
- Tools that create or change a project, save questions, change settings or start a run need
  the operator's explicit go each time. A run spends Sentl credits.
- Never write a token, an account slug, an organization name or data read from an account into
  this repository.

## The repository is public

- No real client, brand, agency, person or study name anywhere: code, tests, fixtures, examples,
  docs, commit messages. Examples use fictional subjects; the docs use a fictional oat-drink
  brand. Add a deny-list test with the first code milestone.
- No paths from a developer's machine.
- English, plain declarative sentences, no slogans. A sentence that can be deleted without losing
  information is deleted.

## Related skills

- `llm-rep`: the source of the concepts reused here (theme inventory with origins, search demand
  with subject and component volumes kept apart, questions paired in positive and negative, the
  report that tells the method before the results). Its run and judge machinery is replaced here
  by Sentl.
- `sentl-snapshot`: the older one-off check on OpenRouter. Its catalogue moves here with M4, and
  the `snapshot` route (M7) replaces it.
