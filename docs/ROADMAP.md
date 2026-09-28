# Roadmap

Each step introduces one MCP idea. Tick it off, and write what you learned in `LEARNING_LOG.md`.

- [x] **0. Check for an official `.twb` schema.** Found it:
  [tableau/tableau-document-schemas](https://github.com/tableau/tableau-document-schemas),
  with versions up to `2026_2`.
- [ ] **1. Empty server.** `uv` project, a FastMCP server with one trivial tool, registered in the
  client's MCP config. *Concepts: what a server is, stdio transport, how the client discovers tools.*
- [ ] **2. `inspect-workbook`** (read-only). Dashboards, sheets, zones (in pixels), fields and
  captions, actions, filters. Run it on real workbooks (from outside the repo) to learn their
  structure. *Concepts: tool name, description, input schema, structured results.*
- [ ] **3. `validate-workbook`.** Check against the XSD, plus the known load errors in `AGENTS.md`
  and missing captions. Optional: Tableau Cloud's `validateWorkbookAndUpload` endpoint.
  *Concepts: errors the model can act on.*
- [ ] **4. `set-caption`** (first write tool). Lock-file check → backup → patch → field diff →
  validate. *Concepts: write tools, guardrails in code, tool annotations (destructive, idempotent).*
- [ ] **5. Template harvesting.** A helper that diffs two saves of the same workbook and shows the
  XML Desktop produced for one change. It feeds every later write tool.
- [ ] **6. Bigger write tools**, each from a harvested template: `add-filter` (hidden filter
  sheet + multiple-values dropdown), `add-nav-button`, `add-filter-action`, `set-zone-geometry`.
- [ ] **7. Prep flows.** `inspect-flow`, then `create-sql-flow` (Custom SQL input → no-op Clean →
  output) from a known-good `.tfl` template.
- [ ] **8. Package it.** Run from any project; decide stdio vs Docker.
