# Roadmap

Each phase is one branch and one PR, introduces one MCP idea, and ends with an entry in
`LEARNING_LOG.md`. The reasoning behind each phase is in [PLAN.md](PLAN.md) §8.

- [x] **0. Plan.** Research, a grilling session, and the agreed design in `PLAN.md`; MIT licence.
- [ ] **1. Foundation.** `uv` project, `MCPServer` over stdio, the `twb-status` tool, byte-faithful
  load/save, and the `tam roundtrip` command. Registered in Claude Code and pi. Spike: which version
  format Desktop 2026.2 accepts for generated files.
  - [x] Server, `twb-status`, `tam roundtrip`, tests (160/160 corpus workbooks round-trip byte for byte)
  - [x] Registered and connected in Claude Code (Linux)
  - [ ] pi: approve the project server once in an interactive pi session
  - [ ] Mac: `uv tool install -e .` and pi's `ancestorConfigRoots` (`~/QuarterMaster`)
  - [ ] Spike: open `spikes/version_format/out/*.twb` in Desktop 2026.2 and record the results *Concepts: what a server is, stdio, tool schemas
  from type hints, structured output, testing with the in-memory client.*
- [ ] **2. `twb-validate`.** Schema chosen by build, manifest gates, references and identity; one fixture
  per known load error; the `tam://checks` resource. *Concepts: errors the model can act on; resources.*
- [ ] **3. `twb-inspect` and `desktop-open-and-check`.** Read a workbook's structure; open a file in
  Desktop and report its load errors. *Concepts: keeping results small; a tool that reaches another
  machine.*
- [ ] **4. Milestone 1: generate a small dashboard.** `twb-create`, `twb-add-sheet` (first presets),
  `twb-add-dashboard`, house style. Done when the owner's dashboard idea opens clean in Desktop.
  *Concepts: composing small tools into a workflow.*
- [ ] **5+. Decided after milestone 1.** Candidates: patch tools, more chart types, full lint and diff,
  the Tableau Public corpus fetch, Prep flows, the harvest command, evals.
