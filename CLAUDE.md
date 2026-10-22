# CLAUDE.md

This repository is the `sentl-monitor` skill. Today it takes an existing Sentl project into a
study folder (`adopt`) and writes a report after each period of runs, compared with the earlier
periods (`report`), lists the themes to monitor (`brief`) and designs a study from them
(`design`), and creates and updates the study's projects in Sentl (`setup`); it reads and writes
Sentl through Sentl's MCP server. A scheduler can start `report` unattended. Planned: a one-off check (`snapshot`). Start every session by reading, in this order:

1. `README.md`: what the skill does, its routes, its requirements.
2. `ARCHITECTURE.md`: the stages, the files each writes, the MCP calls per route, the
   comparison model, and the gaps in Sentl's MCP.
3. `DEVPLAN.md`: the status line at the top, the decisions taken, the milestones.

The status of the work lives in `DEVPLAN.md` only. This file does not repeat it.

## How to work here

- Plan and execute with the `forge-flow` skill (github.com/GuidanceStudio/forge-flow), one
  milestone at a time, test first.
- Mark a milestone in progress before writing code and done in the same commit as the work.
- Scripts use the Python standard library only. Tests live under `tests/`. The install script
  takes `--force`, `--check`, `--host` and `--uninstall`.

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
  brand. `tests/python/test_no_real_names.py` fails on a denied name, a token-shaped string or a
  home-directory path in any file of the repository.
- The denied names live outside the repository, in the file `SKILL_DENYLIST` names (default
  `~/.config/skill-denylist/digests.txt`), and are never committed, as names or as digests: an
  unsalted digest of a name is disclosed by anyone who guesses the name.
- No paths from a developer's machine.
- English, plain declarative sentences, no slogans. A sentence that can be deleted without losing
  information is deleted.
