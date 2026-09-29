# Plan: building tableau-authoring-mcp

Status: **agreed** (2026-09-29, after a grilling session; decisions in §9). Deferred items live in
[V2.md](V2.md); the phase checklist lives in [ROADMAP.md](ROADMAP.md).

---

## 1. What the previous builds taught us

Sources: agent sessions from two dashboard builds (a referral dashboard, September; a communities dashboard,
late September), their 35 patch scripts (5,355 lines), handoff notes and project lessons.

### 1.1 Load errors (each cost at least one round trip through the owner)

| # | What Tableau Desktop said | Real cause |
|---|---|---|
| 1 | `D2E8DA72 no declaration found for element 'button'` | Invented XML |
| 2 | `D2E8DA72 'dashboards' declares duplicate identity constraint` | Cloned dashboard kept the original's `<simple-id uuid>` |
| 3 | `2805CF18 Dashboard references sheet '…' which has no visual representation` | New sheet missing from its dashboard window's `<viewpoints>` |
| 4 | `Error(1009): value 'on-menu' not in enumeration` | Invalid `<activation type>` on a nav action |
| 5 | `Error(3140): element 'filter' is not allowed for content model (…)` | Child elements in the wrong order inside `<view>` |
| 6 | `D2E8DA72 no declaration found for element 'url-action-type'` / `'manual-sort'` | **Missing manifest entry** (see §3.2); the fix applied at the time was the wrong one |
| 7 | Measure Values table error | No Desktop-made example to copy; unresolved |
| 8 | `00BF554A` replacing a datasource | Unresolved |

A correctly configured XSD check would have caught 1, 2, 4 and 5 before the owner saw them. We tested this
by reintroducing each defect into a Desktop-saved workbook. The rest need the checks in §4.

### 1.2 Silent corruption (no error, wrong result)

- A Desktop re-save and a datasource refresh **dropped script-added captions and a colour palette**.
  Nobody noticed for days.
- A filter card drifted onto a different field whose caption differed only by a trailing space.
- Dropping a filter group broke sync between two sheets: the KPI froze while the table moved.
- `included-values='in-range-or-null'` on an LOD-based date filter let every null through: the KPI counted
  nearly every row while the table showed one.
- Context filters run before FIXED LODs, which silently redefined a "first referral" date.
- Changing canvas height rescales every zone, because geometry is in 0–100,000 units.
- The Prep flow's embedded SQL had doubled comparators (`<<`, `>>=`) that nobody asked for.

### 1.3 Workflow friction

- **Brittle patching.** Scripts located XML with regex anchors; one build had five failed runs in a row on
  "anchor not found". Eight of the 35 scripts are `repair_*` / `fix_*` / `remove_*` follow-ups.
- **False confidence.** A home-grown validator reported "OK" on a file Desktop rejected. A log check
  reported "loaded, no errors" twice while the owner was looking at an error dialog.
- **The owner is the feedback loop.** The agent works on Linux and Desktop runs on the Mac, so errors and
  screenshots travel by copy-paste.
- **No examples to copy** for URL actions or Measure Values tables. The agent guessed from the schema and
  the guess failed.
- **Cloud gaps.** The official Tableau MCP can't publish a datasource or a flow, and its flow tools are
  switched off.

---

## 2. What already exists

| Project | What it is | What we take from it |
|---|---|---|
| [tableau/tableau-mcp](https://github.com/tableau/tableau-mcp) (official) | Cloud tools. `publish-workbook` validates a TWB through the REST API first. Also has a **Desktop mode** (`list-instances`, `get-workbook-xml`, `apply-workbook`, `check-for-user-changes`) that talks to a running Desktop through an "Agent API" (`~/.tableau/agent-manifest.json`, port 8765) | Don't duplicate any of it. The Agent API isn't present in the installed Desktop 2026.2; when it ships, `apply-workbook` becomes the best load test (§8, Phase 7) |
| [tableau/tableau-plugin](https://github.com/tableau/tableau-plugin) (Codex plugin, `tableau-workbook-authoring` skill) | Cloud-first authoring: download → edit XML → validate → publish → render. Bundles XSDs 2018.1–2026.2, a validator, 60 chart templates (`.tbm`), **62 Desktop before/after diffs**, snippets from **432 Tableau test workbooks**, and `inspect`/`add-encoding`/`add-filter` commands that only emit shapes seen in real Desktop XML ("fail closed") | Its philosophy matches ours. Reuse its schema-version sniffing and known schema-bug suppressions; mine its corpus for templates (with attribution) |
| [tableau/tableau-document-schemas](https://github.com/tableau/tableau-document-schemas) | Official XSDs. Documents `<ManifestByVersion/>` and the REST **Validate Workbook** endpoints (Cloud June 2026 / Server 2026.2), which do semantic validation ("will it open") | Syntactic baseline. The REST endpoint is the semantic oracle |
| [cwtwb](https://github.com/aidatacooper/cwtwb) | Python engine + MCP for generating workbooks from specs; function-name check on calcs; cloud validation | Ideas only: it's **AGPL-3.0**, so no code |
| [tableau-local-mcp](https://github.com/Evgenzh2007/tableau-local-mcp) | 80 tools, edits in memory, saves on request | A warning: tool sprawl, and in-memory state that Desktop can overwrite |
| [tableau-public-authoring-mcp](https://github.com/andyyaro/tableau-public-authoring-mcp) | Generates from a spec and validates by **opening in Tableau Public** on macOS | Opening in the app is the real test; `doctor` command for prerequisites |
| [tableau-lineage](https://github.com/andey0Saikiran/tableau-lineage) | Audit: dead fields, duplicate calcs, performance lint, **semantic diff** of versions | A semantic diff is how to catch dropped captions (§1.2) |

**Where we fit:** the only one that **patches existing Desktop-made workbooks on disk** with guardrails,
evidence-based templates and manifest-aware validation. Others generate from scratch or work Cloud-first.

---

## 3. Technical findings that shape the design

### 3.1 Desktop always writes `version='18.1'`
All 113 Desktop-saved workbooks we indexed (builds 2020.3–2026.2) say `version='18.1'`. The real format
comes from the `<!-- build 20262.… -->` comment or `source-build`. Validate against the XSD for that
build (2026.2 for us), not by the `version` attribute.

### 3.2 Features are gated by the manifest
Desktop-saved files list feature flags in `<document-format-change-manifest>`. Elements added after the
18.1 format only load if their entry is present. Evidence from 109 workbooks:

| Element used | Manifest entry every Desktop file with it also has |
|---|---|
| `<manual-sort>`, `<natural-sort>`, `<computed-sort>` | `SortTagCleanup` (58 of 58 files with `manual-sort`) |
| `<nav-action>` | `NavigationAction` |
| `<button>`, `dashboard-object` zones | `BasicButtonObject` (+ `BasicButtonObjectTextSupport` for caption fonts) |
| `<edit-parameter-action>` | `ParameterAction` (+ `ParameterActionClearSelection`) |
| `<shelf-sort-v2>` | `IntuitiveSorting`, `IntuitiveSorting_SP2` |
| `<single-value-per-nest-shelf-sort>` | `SingleValuePerNestSorting` |
| rounded corners | `_.fcp.DashboardRoundedCorners.true...DashboardRoundedCorners` |

This explains error 6. `manual-sort` is valid; the workbook just lacked `SortTagCleanup`. It also means
**the XSD can pass a file Desktop will reject**, and no public tool checks this. We mine these rules from
the corpus, ship them as data with evidence counts, and refine them from harvest diffs.

### 3.3 Feature-flag prefixes
Newer attributes and elements appear as `_.fcp.<Flag>.true...<name>`. Keep them byte-for-byte; strip them
only inside the validator.

### 3.4 Identity and cross-references the XSD doesn't cover
The XSD enforces unique dashboard `simple-id`s. It doesn't check:
- that names are unique;
- that every dashboard zone's sheet has a `<window>` **and** a `<viewpoint>`;
- that action sources resolve;
- that filter groups are consistent;
- that each column instance is declared in `<datasource-dependencies>`.

### 3.5 A corpus of Desktop-saved files exists
- **Local:** 113 workbooks from the Mac and the tries (in a local corpus folder outside the repo, never
  committed).
- **The plugin's** diffs and snippet index.
- **Tableau Public:** `https://public.tableau.com/workbooks/<name>.twb` downloads work.
- **Already covered:** nav buttons, nav actions, filter actions, parameter actions, filter cards, Measure
  Names/Values tables (48 files).
- **Not covered locally:** Go-to-URL actions. A Tableau Public search found them: Tableau writes them as
  an empty `<link caption=… expression='https://…' />`, with **no** `url-action-type` child.
- Tableau Public re-saves downloads in its current format (a 2024 workbook came back as build 2026.2), so
  public files are Tableau-written XML in exactly the format we target.

### 3.6 Three ways to find out whether Tableau will load a file
1. **REST Validate Workbook.** The best oracle, but it needs Cloud auth, which lives in tableau-mcp; that
   server only exposes it inside `publish-workbook`.
2. **Desktop's own log** (`~/Documents/My Tableau Repository/Logs/log*.txt`, JSON lines with
   `detailed-error-msg` and `show-detailed-error-dialog`), read on the Mac after opening the file. Works
   today. It needs care: rotated files, an already-open workbook, and matching the open timestamp. That
   is what went wrong in §1.3.
3. **Desktop Agent API** `apply-workbook`, once Desktop ships it.

### 3.7 MCP platform facts (September 2026)
- Spec **2026-07-28**. Python SDK **`mcp` 2.2**, where `FastMCP` is now **`MCPServer`**
  (`from mcp.server import MCPServer`). `AGENTS.md` still says FastMCP; update it.
- Tools can return typed results (Pydantic → `outputSchema` + `structuredContent`) alongside a text summary.
- `raise ToolError(...)` gives the model a readable, recoverable error. Other exceptions become opaque
  protocol errors.
- The protocol has no session. State between calls needs an explicit handle. For us the file on disk is
  the state.
- Testing: `async with Client(server) as c: await c.call_tool(...)` runs in memory, with no subprocess.

---

## 4. Design principles

Sources: the MCP spec; Anthropic's
[Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents);
AWS/Workato MCP guidelines; and the failures above.

1. **Few, workflow-sized tools.** Aim for about 8 in v1 and at most about 20 in total, not 80. One
   `twb-sync-filter` beats five low-level XML tools.
2. **The model speaks captions, the server speaks XML.** Tools take `"Referral Date"`, `"Detail"` or pixel
   sizes. The server resolves them to `[sqlproxy.x].[none:FIELD:nk]`, simple-ids and 0–100,000 units. The
   model never writes column-instance tokens, which were the source of several errors.
3. **Generation reuses the patch tools.** A new workbook starts from a Tableau-proven skeleton and grows
   through the same add-sheet / add-dashboard operations as edits. There's no separate "write a whole
   workbook" code path, so no invented XML.
4. **Disk is the only state.** Every call reads the file, patches it and writes it. There's no in-memory
   workbook, because Desktop edits the same file.
5. **Every write tool runs the same pipeline, in code:**
   1. refuse if the file is open in Desktop;
   2. back up to `<name>.before-<change>.twb`;
   3. patch with lxml, never regex;
   4. semantic diff: refuse if a field, caption or sheet disappeared;
   5. validate (§5);
   6. report what changed.
6. **Round-trip fidelity.** Loading and saving an unchanged workbook must produce the same bytes (single
   quotes, attribute order, whitespace, fcp names). Otherwise every diff is noise, and harvesting and
   review stop working. This is the first test.
7. **Templates come from evidence.** Each template records its provenance: corpus file, harvest diff or
   plugin example. Unknown shapes fail closed with a message saying what to harvest.
8. **Errors the model can act on.** Return a check id, element path, line, reason and fix, plus
   "did you mean" for names. No stack traces.
9. **Typed results plus a short text summary.** `inspect` takes `detail: summary|full` and a `section`
   filter, so results stay small (Claude Code caps tool output at about 25k tokens).
10. **Honest annotations.** `readOnlyHint` on read tools. `openWorldHint: false` everywhere.
   `idempotentHint` only where a second run is a no-op.
11. **No data values leave the file.** Inspect returns metadata, not extract rows. Logs go to stderr.
    Writes are refused outside configured roots.
12. **New failure → fixture + check, before the fix.** (AGENTS.md rule 6.)

---

## 5. Validation layers (the core of the server)

| Layer | Checks | Catches (from §1) |
|---|---|---|
| L0 Parse | Well-formed XML, encoding | — |
| L1 Schema | XSD chosen by build; fcp names normalised; the plugin's known XSD bugs suppressed | 1, 2, 4, 5 |
| L2 Manifest gates | Mined element→manifest rules (§3.2) | 6 |
| L3 Attested shapes | Element, attribute and enum values seen in Desktop-saved files; anything unseen is a **warning** | 6, 7 (early warning) |
| L4 References and identity | Unique names and simple-ids; windows and viewpoints; zone→sheet; action sources and targets; filter groups; datasource and column-instance declarations | 2, 3 |
| L5 Semantic lint | Raw DB names; trailing-space and near-duplicate captions; `in-range-or-null` on LOD fields; context filter + FIXED LOD; KPI/table filter parity | §1.2 items |
| L6 Oracle | Desktop open-and-check (Mac) or REST Validate Workbook | anything else |

The validator is also usable as a CLI (`uv run tam validate file.twb`) for scripts and CI.

---

## 6. Tool catalogue

Every tool name starts with `twb-` or `tfl-`, so the model can tell local-file tools apart from
tableau-mcp's Cloud tools (`get-workbook`, `list-worksheets`, `publish-workbook`). The server never
connects to Cloud: when a tool needs a published datasource's fields, the agent fetches them with
tableau-mcp's `get-datasource-metadata` and passes the JSON in. A Prep field-contract JSON, or an existing
connected workbook, also works.

**Read and check** (safe on any file, including workbooks you're editing elsewhere)
- `twb-status`: format, Tableau build, whether Desktop has the file open, backups.
- `twb-inspect`: datasources and fields (name, caption, role, type, hidden), sheets, dashboards with zones
  in pixels, actions, filter groups, parameters. Takes `section` and `detail`.
- `twb-describe`: one sheet or dashboard in depth.
- `twb-validate`: the layered checks in §5.
- `twb-diff`: semantic diff of two versions; catches dropped captions and palettes after a Desktop save.
- `desktop-open-and-check`: open the file in Desktop on the Mac (locally, or over SSH from Linux after
  Syncthing catches up) and report this workbook's load errors from Desktop's log. Called only when the
  agent chooses; refuses if Desktop already has the file open.

**Generate** (milestone 1)
- `twb-create`: new workbook from a Tableau-proven skeleton, connected to a published datasource (field
  list passed in) or a CSV/Hyper file.
- `twb-add-sheet`: one shelf-based tool: mark type, rows, columns, colour / size / label / detail /
  tooltip, sort, filters, all written as captions like `SUM(Referrals)`. Presets fill the shelves: `kpi`,
  `table`, `bar`, `stacked-bar`, `line`, `map`.
- `twb-add-dashboard`: a container tree (rows and columns, sized in pixels) plus house-style presets
  (header, KPI row, main area, filter panel). The server converts pixels to Tableau's units.

**Patch** (after milestone 1; order decided then)
- `twb-set-captions`, `twb-set-field-metadata`, `twb-sync-filter`, `twb-set-filter`,
  `twb-add-calculated-field`, `twb-duplicate-dashboard` / `twb-duplicate-sheet`, `twb-add-action`
  (filter, highlight, URL, navigate, parameter), `twb-add-nav-button`, `twb-set-zone-geometry` /
  `twb-set-canvas-size`, `twb-add-zone`, `twb-set-colors`, `twb-repoint-datasource`.
- Chart types beyond the first set, from the corpus: area, pie, scatter, shape, Gantt, highlight table,
  density map, polygon, dual axis, reference lines. Sankey is v2.

**Prep flows** (later): `tfl-inspect`, `tfl-validate`, `tfl-set-custom-sql`, `tfl-new-from-template`.

**Resources and prompts.** Resource `tam://checks` (every check and the Desktop error it prevents),
resource `tam://templates` (templates and their provenance), prompt `triage-load-error`. pi exposes
resources as tools, but anything essential must also be reachable as a tool.

**Dev commands (CLI `tam`, not MCP).** `tam roundtrip` (check byte-faithful load/save over a folder),
`tam corpus fetch` (gap-first Tableau Public download, §3.5), `tam corpus index` (rebuild the manifest-gate
and attested-shape data), `tam harvest before.twb after.twb` (turn a Desktop change into a template
candidate).

**Boundaries.** Workbooks you're actively editing elsewhere (such as the communities build) are read-only
for this server: inspect, validate and diff only. Write tools run on copies, or on files you name for it.

---

## 7. Stack and package layout

Python 3.12+, official `mcp` SDK ≥ 2.2 (`MCPServer`), lxml, Pydantic v2, pytest with the in-memory
`Client`, stdio transport. `tableauhyperapi` is an optional extra for CSV → Hyper. Installed with
`uv tool install` on each machine and listed once in the synced `~/Quartermaster/.mcp.json`; pi finds it
through an `ancestorConfigRoots` entry on each machine. Configuration is by environment variable (corpus
path, style file, Mac SSH host, path mapping); there are no secrets.

```
src/tableau_authoring_mcp/
  server.py              MCPServer; registers tools (thin wrappers only)
  cli.py                 `tam` dev commands
  twb/
    document.py          load/save with byte-faithful round trip; .twbx unzip/rezip
    status.py            build detection, lock files, backups
    model.py             read model: fields, sheets, dashboards, zones, actions, filters
    resolve.py           caption → internal names; column-instance synthesis
    ids.py               simple-ids, action names, zone ids, filter-group ids
    geometry.py          px ↔ units
    guard.py             lock check, backup, semantic diff
    validate/            xsd.py, manifest.py, attested.py, refs.py, lint.py
    generate/            skeletons, sheet presets, dashboard layouts
    patches/             one module per write tool
  tfl/                   flow zip + JSON
  desktop/               log reader, open-and-check
  data/                  manifest_gates.json, attested_shapes.json, templates/*.xml (+ provenance)
styles/house.toml        house style values (colours, radius, sizes, naming)
schemas/                 vendored Tableau XSDs (Apache-2.0, with NOTICE)
tests/fixtures/          synthetic, tiny; one fixture per known error
```

---

## 8. Phases

Each phase is one branch and one PR, introduces one MCP concept, and ends with a `LEARNING_LOG.md` entry.
The checklist is in [ROADMAP.md](ROADMAP.md).

| Phase | Deliverable | MCP concept | Done when |
|---|---|---|---|
| 0 | Agreed plan in the docs; MIT licence | — | Merged |
| 1 | `uv` project, `MCPServer` over stdio, `twb-status`, byte-faithful load/save, `tam roundtrip`; version-format spike files | Server, stdio, tool schema from type hints, structured output, in-memory test client | Byte-identical round trip on fixtures and every corpus workbook; the server answers `twb-status` in Claude Code and pi |
| 2 | `twb-validate`: schema by build, manifest gates, references and identity; one fixture per §1.1 error; `tam://checks` | Actionable `ToolError`s; resources | Every corpus workbook clean; every §1.1 fixture caught |
| 3 | `twb-inspect`, `desktop-open-and-check` | Keeping results small; a tool that reaches another machine | Answers "what's on dashboard X"; a Desktop error dialog is reported, with no false "OK" |
| 4 | **Milestone 1**: `twb-create`, `twb-add-sheet` (first presets), `twb-add-dashboard`, house style | Composing small tools into a workflow | The owner's dashboard idea, generated on its datasource, opens clean in Desktop |
| 5+ | Decided after milestone 1: patch tools, more chart types, full lint and diff, corpus fetch, Prep flows, harvest CLI, evals | — | — |

The spike in Phase 1: open a `ManifestByVersion` (26.2) file and an 18.1 file with explicit manifest
entries in Desktop 2026.2. Whichever loads and survives a save becomes the format for generated workbooks.

---

## 9. Decisions (grilling session, 2026-09-29)

| Topic | Decision |
|---|---|
| Scope | Patch existing Desktop-saved files **and** generate new workbooks (generation reuses the patch tools) |
| Data sources for generation | Published Cloud datasources; CSV / Hyper files |
| First charts | KPI, text table, bar / stacked bar, line, map; then every type in the corpus; Sankey in v2 |
| Chart tool | Shelves + presets |
| Layout | Container tree in pixels + house-style presets |
| Version format | Decided by the Phase 1 spike; targets are Desktop 2026.2 and Tableau Cloud |
| Where it runs | Linux and the Mac; the Desktop check reaches the Mac over SSH |
| Desktop check | Separate tool, only when the agent calls it |
| Cloud validation | v2: a `validate-workbook` PR to tableau-mcp ([V2.md](V2.md)) |
| Field lists | Passed in by the agent (from tableau-mcp), or read from a field contract or connected workbook |
| In-flight workbooks | Read-only |
| Code | Our own; Tableau's XSDs vendored; Tableau's plugin used as reference and credited |
| Who writes | Claude implements and explains; the owner reviews each phase's PR |
| Review | One branch and PR per phase |
| Dev machine | Either machine, never both at once (`.git` syncs through Syncthing) |
| Tool names | `twb-` / `tfl-` prefixes |
| Licence | MIT |
| Corpus | Mac copy + gap-first Tableau Public download (300–500, after milestone 1), at `~/.local/share/tableau-corpus` on Linux only; only derived rules and counts are committed |
| Harvesting | Batched Desktop sessions from a checklist when the corpus lacks an example |
| House style | Company values committed, scrubbed of internal references, in `styles/house.toml` |
| Clients | Claude Code and pi |
| Stack | Python + official SDK (§7) |
| Milestone 1 | Generate a small dashboard; the idea comes from the owner. Milestone 2 decided afterwards |
