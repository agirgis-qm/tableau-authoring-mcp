@AGENTS.md

## Claude Code specifics

- The Cloud side is the `tableau` MCP server (official `tableau-mcp`, local Docker). Use it to look
  up published datasources and to publish; use this repo's server for local files.
- After a write tool changes a workbook, open it for the owner to review:
  `open -b com.tableausoftware.tableaudesktop "<absolute path>.twb"`.
