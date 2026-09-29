"""The MCP server: registers tools and runs over stdio.

Tools here are thin wrappers. The work lives in `twb/`; this module turns results into typed tool output
and expected failures into `ToolError`s, whose messages the model sees and can act on. Any other exception
would reach the model as an opaque protocol error, so every failure a user can cause must be a ToolError.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field

from . import __version__
from .twb.document import DocumentError
from .twb.status import WorkbookStatus, workbook_status

INSTRUCTIONS = """\
Inspects, validates, patches and generates LOCAL Tableau files (.twb, .twbx). It never talks to Tableau Cloud:
use the separate `tableau` server (tableau-mcp) to find published datasources, fetch their field metadata,
publish, or render views. Tool names start with twb- (workbooks) or tfl- (Prep flows).
Before changing a workbook, call twb-status: if Tableau Desktop has it open, ask the user to close it first.
"""

mcp = MCPServer("tableau-authoring", instructions=INSTRUCTIONS, version=__version__)

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

WorkbookPath = Annotated[
    str, Field(description="Absolute (or ~-relative) path to a .twb or .twbx file on this machine")
]


@mcp.tool(name="twb-status", title="Workbook status", annotations=READ_ONLY)
def twb_status(path: WorkbookPath) -> WorkbookStatus:
    """Report what a workbook is and whether it's safe to change.

    Returns the Tableau build that saved it, whether Tableau Desktop has it open (from its lock file),
    backups made before earlier changes, and counts of datasources, worksheets and dashboards. Read-only.
    Call it before any write, and whenever the user may have saved the file in Desktop since you last looked.
    """
    try:
        return workbook_status(path)
    except DocumentError as e:
        raise ToolError(str(e)) from e
    except OSError as e:
        raise ToolError(f"Couldn't read {path}: {e.strerror}. Check the path and permissions.") from e


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
