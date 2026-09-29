# AGENTS.md

Instructions for any coding agent (Claude Code, pi, Codex, ...) working in this repo.

## What this is

A Python MCP server that inspects, validates, patches and generates local Tableau files (`.twb`, `.tfl`).
The agreed plan is in `docs/PLAN.md`; deferred work is in `docs/V2.md`.
It pairs with the official `tableau/tableau-mcp`, which handles Tableau Cloud (reading, querying,
publishing). Never duplicate Cloud features here.

It is also a **learning project**: the owner is learning how MCP servers work. When adding
something, explain the MCP concept it introduces, and add a dated entry to
`docs/LEARNING_LOG.md`.

## Stack

- Python 3.12+, managed with `uv`. Official MCP Python SDK, `mcp` ≥ 2.2. The server class is `MCPServer`
  (`from mcp.server import MCPServer`); v2 renamed `FastMCP`, so ignore older examples that use it.
- XML via `lxml` (keeps attribute order and supports XSD validation).
- Schemas: `tableau/tableau-document-schemas`, vendored. Pick the XSD from the workbook's
  `<!-- build … -->` comment or `source-build`, never from `version`: Desktop always writes `version='18.1'`.
- Tests: `pytest`, against synthetic fixtures in `tests/fixtures/`.

## Tool design rules

1. **Small, specific tools**, named `twb-…` / `tfl-…` (`twb-sync-filter`, `twb-set-captions`): never a
   "write the whole workbook" tool. Never regenerate an existing workbook. New workbooks start from a
   Tableau-proven skeleton and grow through the same tools.
2. **No invented XML.** A template must come from XML Tableau wrote: a Desktop change (save, one change,
   save, diff), a Desktop-saved corpus file, or a Tableau Public download. Record where each template
   came from in `docs/templates.md`.
3. **Mind the manifest.** Elements added after the 18.1 format only load if their
   `<document-format-change-manifest>` entry is present (e.g. `<manual-sort>` needs `SortTagCleanup`,
   `<nav-action>` needs `NavigationAction`). A write that adds such an element adds the entry too.
4. **Every write tool, in order:** refuse if Tableau has the file open (`.~<name>__*.twbr` lock
   file next to it) → back up to `<name>.before-<change>.twb` → patch → compare the field list
   before/after and refuse if anything disappeared → validate → report what changed.
5. **Errors the model can act on.** Return the element, the reason, and the fix. Not a stack trace.
6. **Pixels in, units out.** Dashboard zone geometry is stored in 0–100,000 units relative to the
   canvas; tools accept pixels and convert.
7. **New failure → new check.** When Tableau rejects a file, add a check to `validate-workbook`
   and a fixture that reproduces it, before fixing the tool.

## Known Tableau load errors (seed the checks)

| Error | Cause |
|---|---|
| `D2E8DA72 no declaration found for element '<x>'` | Invented or misplaced element (fails XSD), **or** a valid element whose manifest entry is missing (passes XSD) |
| `D2E8DA72 ... duplicate identity constraint` | Duplicate dashboard / window names or ids |
| `2805CF18 Dashboard references sheet '<x>' which has no visual representation` | Zone points at a missing worksheet, or one without a `<window>` |
| `00BF554A` on replacing a datasource | Unresolved; investigate before building a replace-datasource tool |

Also flag: visible fields with raw database names and no caption (e.g. `ORDER_STATUS_CD`).

## Public repo: data rules

- Never commit real workbooks, flows, extracts, SQL against company tables, connection strings,
  site URLs, people's names, or query results. `.gitignore` blocks Tableau file types; fixtures
  must be synthetic and tiny.
- Real workbooks for testing stay outside the repo; pass their paths at runtime. The corpus lives in
  `~/.local/share/tableau-corpus` (Linux only, outside Syncthing); commit only rules and counts derived
  from it.
- House style values may be committed (`styles/house.toml`), but no internal links, company or people's
  names, or workbook names.
- Workbooks the owner is editing elsewhere are read-only for this server: write tools run on copies.

## Workflow

- Plan, get approval, then implement. One branch and one PR per phase; the owner reviews and merges.
- Work from one machine at a time: this repo (including `.git`) syncs between Linux and the Mac.
- Tool changes: add or update a test first; run `uv run pytest`.
