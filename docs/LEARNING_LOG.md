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

## 2026-09-29: Phase 1, a server with one tool

**How the pieces connect**
- An MCP server is just a program. The client (Claude Code, pi) starts it as a subprocess and they talk
  JSON-RPC over its stdin and stdout; that's the **stdio transport**. So a stdio server must never print to
  stdout: stdout *is* the protocol. Logs go to stderr.
- The client finds the server through config: a `.mcp.json` with `"command": "tableau-authoring-mcp"`.
  Claude Code reads `.mcp.json` from the project and its parent folders; pi reads it too once a parent is
  listed in `settings.ancestorConfigRoots`, and asks you to approve each project server first.
- On connect the client calls `tools/list`. What the model sees for `twb-status` is built entirely from the
  Python function: its name and title from the decorator, its description from the docstring, the input
  schema from the type hints (`Annotated[str, Field(description=...)]`), and an **output schema** from the
  returned Pydantic model.

**Results and errors**
- Returning a Pydantic model gives two things: `structuredContent` (typed JSON matching the output schema,
  for programs) and a text copy (for models and older clients).
- `raise ToolError("File not found: … Check the path")` comes back as a normal result with `isError: true`
  and that message, which the model can act on. Any other exception is an opaque protocol error, so every
  failure a user can cause is turned into a ToolError.
- Annotations (`readOnlyHint=True`, `openWorldHint=False`) tell the client the tool only reads local
  files, so it can skip or relax confirmation prompts. They're hints, not enforcement.

**Testing**
- `async with Client(mcp) as c: await c.call_tool(...)` runs the real server in memory: same tool list,
  same schemas, same error handling, no subprocess. A separate check launches the installed command over
  stdio, the way the clients do.

**The file layer**
- Re-serializing a Tableau workbook with lxml changed bytes nobody touched: only 35 of 182 files came back
  identical (CDATA, CRLF line endings, entity choices). So a `Document` records where every node sits in
  the original bytes (expat reports offsets) and copies unchanged nodes verbatim; only changed nodes are
  serialized, in Tableau's style. Result: 160 of 160 corpus workbooks round-trip byte for byte even when
  every element is rebuilt from its parts. With every start tag re-serialized by our code, 154 of 160
  still match; the 6 that don't were written by our old regex scripts, not by Tableau.
- Desktop's `.~name__pid.twbr` files are autosaves that outlive crashes. From Linux we can't tell a live
  lock from a stale one, so `twb-status` says "unknown" rather than guessing, and mentions the lock's age.
