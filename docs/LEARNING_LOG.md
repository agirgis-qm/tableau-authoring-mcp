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
