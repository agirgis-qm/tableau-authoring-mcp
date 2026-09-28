# AGENTS.md

Instructions for any coding agent (Claude Code, pi, Codex, ...) working in this repo.

## What this is

A Python MCP server that inspects, validates, and patches local Tableau files (`.twb`, `.tfl`).
It pairs with the official `tableau/tableau-mcp`, which handles Tableau Cloud (reading, querying,
publishing). Never duplicate Cloud features here.

It is also a **learning project**: the owner is learning how MCP servers work. When adding
something, explain the MCP concept it introduces, and add a dated entry to
`docs/LEARNING_LOG.md`.

## Stack

- Python, managed with `uv`. Official MCP Python SDK (`mcp`, `FastMCP`).
- XML via `lxml` (keeps attribute order and supports XSD validation).
- Schemas: `tableau/tableau-document-schemas` (pin the version that matches the Desktop release).
- Tests: `pytest`, against synthetic fixtures in `tests/fixtures/`.

## Tool design rules

1. **Small, specific tools.** `add-filter`, `set-caption`, `add-nav-button`: never a
   "write the whole workbook" tool. Patch; never regenerate.
2. **No invented XML.** A write tool's template must come from a real Desktop-made change
   (save, one change, save, diff). Record where each template came from in `docs/templates.md`.
3. **Every write tool, in order:** refuse if Tableau has the file open (`.~<name>__*.twbr` lock
   file next to it) → back up to `<name>.before-<change>.twb` → patch → compare the field list
   before/after and refuse if anything disappeared → validate → report what changed.
4. **Errors the model can act on.** Return the element, the reason, and the fix. Not a stack trace.
5. **Pixels in, units out.** Dashboard zone geometry is stored in 0–100,000 units relative to the
   canvas; tools accept pixels and convert.
6. **New failure → new check.** When Tableau rejects a file, add a check to `validate-workbook`
   and a fixture that reproduces it, before fixing the tool.

## Known Tableau load errors (seed the checks)

| Error | Cause |
|---|---|
| `D2E8DA72 no declaration found for element '<x>'` | Invented or misplaced element (fails XSD) |
| `D2E8DA72 ... duplicate identity constraint` | Duplicate dashboard / window names or ids |
| `2805CF18 Dashboard references sheet '<x>' which has no visual representation` | Zone points at a missing worksheet, or one without a `<window>` |
| `00BF554A` on replacing a datasource | Unresolved; investigate before building a replace-datasource tool |

Also flag: visible fields with raw database names and no caption (e.g. `ORDER_STATUS_CD`).

## Public repo: data rules

- Never commit real workbooks, flows, extracts, SQL against company tables, connection strings,
  site URLs, people's names, or query results. `.gitignore` blocks Tableau file types; fixtures
  must be synthetic and tiny.
- Real workbooks for testing stay outside the repo; pass their paths at runtime.

## Workflow

- Plan, get approval, then implement. Commit only when asked.
- Tool changes: add or update a test first; run `uv run pytest`.
