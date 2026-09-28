# tableau-authoring-mcp

An MCP server for **safely editing local Tableau files**: `.twb` workbooks (Tableau Desktop) and
`.tfl` flows (Tableau Prep). It is also a learning project: how MCP servers work, built one tool at
a time.

It complements, and does not replace, the official
[tableau/tableau-mcp](https://github.com/tableau/tableau-mcp):

| | `tableau-mcp` (official) | `tableau-authoring-mcp` (this repo) |
|---|---|---|
| Works on | Tableau Cloud / Server | Files on your machine |
| Does | Read datasources, views, workbooks; query data; publish | Inspect, validate, and patch `.twb` / `.tfl` files |

An agent connects to both: this server builds the file, you check it in Desktop or Prep, and
`tableau-mcp` publishes it.

## Why

Letting an agent edit workbook XML with general file tools works, but slowly. It invents
elements, breaks ids, loses fields, and learns Tableau's rules one load error at a time. This
server moves those rules into code the agent cannot skip:

- **Templates from examples.** Each write tool emits XML copied from a change made in Tableau
  Desktop (save, make one change, save, diff). Nothing invented.
- **Checks from errors.** Every load error or review defect becomes a check in
  `validate-workbook`, including validation against Tableau's published
  [document schemas](https://github.com/tableau/tableau-document-schemas).
- **Guardrails on every write.** Refuse while Desktop has the file open, back up first, patch
  rather than regenerate, refuse if a field disappears, validate after.

What it does not do: drive the Tableau apps (there is no API for that), or make your calculations
correct. You still do the visual check and reconcile the numbers.

## Status

Nothing built yet. See [docs/ROADMAP.md](docs/ROADMAP.md) for the plan and
[docs/LEARNING_LOG.md](docs/LEARNING_LOG.md) for what has been learned along the way.

## Data policy

This repo is public. No real workbooks, flows, extracts, connection details, or data go in it;
`.gitignore` blocks them. Tests use small synthetic fixtures only.
