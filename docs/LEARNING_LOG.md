# Learning log

Dated notes on how MCP works, and what Tableau's file formats taught us. Newest at the bottom.

## 2026-09-28: What an MCP server is

- An MCP server gives the model a menu of **tools**. For each one, the model sees only its name,
  description, and input schema, never the code.
- Flow: the model asks to call a tool → the client (Claude Code, pi, ...) forwards the call → the
  server runs real code → it returns text or JSON → the model reads that and decides what's next.
- Tools can give **context** (read tools) or **control** (write tools). The model can only do what
  the tools allow, in the way they allow. Rules written into a tool's code can't be skipped;
  rules written in a prompt or doc can.
- MCP also has *resources* (static context) and *prompts* (reusable templates). Tools are most of
  what matters.
- Servers compose: a client can connect to several at once. That is why this is a separate server
  next to the official `tableau-mcp`, not a fork of it.

## 2026-09-28: Why build this

A previous dashboard build had an agent edit `.twb` XML with general file tools. Most of the
delays were **file-format** problems a tool could have prevented: invented elements, duplicate
ids, zones pointing at missing sheets, Desktop saving over script edits, fields silently dropped,
pixel vs unit confusion. The **logic** problems (a KPI not matching its table because context
filters run before FIXED LODs) are not something a tool fixes; they still need reconciling
against the source.

Two ways to learn Tableau's rules:
- **Examples give templates** (what to write): save, make one change in Desktop, save, diff.
- **Errors give checks** (what to refuse): every rejection becomes a validation rule.

## 2026-09-29: Research, and what shaped the plan

**MCP, as of the 2026-07-28 spec and Python SDK v2.2**
- The high-level server class is now `MCPServer`; v1 called it `FastMCP`.
- A tool's input schema comes from its Python type hints. If it returns a Pydantic model, the SDK also
  publishes an **output schema**, and each result carries typed data (`structuredContent`) next to the
  usual text.
- Two kinds of error: raising `ToolError` sends a readable message the model can act on; any other
  exception becomes an opaque protocol error. So every expected failure should be a `ToolError`.
- The protocol has no session. If calls need shared state, a tool returns a handle and later calls pass
  it back. For us the state is simply the file on disk.
- Tools carry **annotations** (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`).
  They're hints for the client, not guarantees.
- Anthropic's advice on tools for agents: few workflow-sized tools rather than one per API call, human
  names instead of IDs, small results, and errors that say how to fix the call.

**Tableau's file format**
- Desktop always writes `version='18.1'`, whatever the release. The real format is in the
  `<!-- build … -->` comment.
- Features newer than that format are switched on in `<document-format-change-manifest>`. A valid
  element can still fail to load if its entry is missing: `<manual-sort>` needs `SortTagCleanup`. That
  was the real cause of a load error in the communities build.
- Passing the XSD is necessary, not sufficient. In a test, the XSD caught 4 of 7 historical load errors;
  the rest need reference and manifest checks.
- Tableau's own Codex plugin and tableau-mcp already hold a lot of prior art: XSDs for every release,
  Desktop before/after diffs, and a Desktop mode in tableau-mcp that will be able to load XML straight
  into Desktop once Desktop supports it.
