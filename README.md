# tableau-authoring-mcp

An MCP server for **safely editing and generating local Tableau files**: `.twb` workbooks (Tableau
Desktop) and `.tfl` flows (Tableau Prep). It is also a learning project: how MCP servers work, built one tool at
a time.

It complements, and does not replace, the official
[tableau/tableau-mcp](https://github.com/tableau/tableau-mcp):

| | `tableau-mcp` (official) | `tableau-authoring-mcp` (this repo) |
|---|---|---|
| Works on | Tableau Cloud / Server | Files on your machine |
| Does | Read datasources, views, workbooks; query data; publish | Inspect, validate, patch and generate `.twb` / `.tfl` files |

An agent connects to both: this server builds the file, you check it in Desktop or Prep, and
`tableau-mcp` publishes it.

## Why

Letting an agent edit workbook XML with general file tools works, but slowly. It invents
elements, breaks ids, loses fields, and learns Tableau's rules one load error at a time. This
server moves those rules into code the agent cannot skip:

- **Templates from examples.** Each write tool emits XML that Tableau itself wrote: a change made in
  Desktop (save, one change, save, diff), or a Tableau-saved example workbook. Nothing invented.
- **Checks from errors.** Every load error or review defect becomes a check in
  `validate-workbook`, including validation against Tableau's published
  [document schemas](https://github.com/tableau/tableau-document-schemas).
- **Guardrails on every write.** Refuse while Desktop has the file open, back up first, patch
  rather than regenerate, refuse if a field disappears, validate after.

What it does not do: make your calculations correct. You still do the visual check and reconcile the
numbers. It can open a file in Desktop and read back any load errors, but it doesn't click around in
the apps.

## Status

In development. The agreed design is in [docs/PLAN.md](docs/PLAN.md), progress in
[docs/ROADMAP.md](docs/ROADMAP.md), deferred ideas in [docs/V2.md](docs/V2.md), and what has been
learned along the way in [docs/LEARNING_LOG.md](docs/LEARNING_LOG.md).

## Data policy

This repo is public. No real workbooks, flows, extracts, connection details, or data go in it;
`.gitignore` blocks them. Tests use small synthetic fixtures only.
