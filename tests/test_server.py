import pytest
from mcp import Client

from tableau_authoring_mcp.server import mcp

pytestmark = pytest.mark.anyio


async def test_server_lists_twb_status_as_read_only():
    async with Client(mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    tool = tools["twb-status"]
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.open_world_hint is False
    assert "path" in tool.input_schema["required"]
    assert "desktop" in tool.output_schema["properties"]


async def test_twb_status_returns_structured_content(minimal):
    async with Client(mcp) as client:
        result = await client.call_tool("twb-status", {"path": str(minimal)})
    assert result.is_error is False
    assert result.structured_content["worksheets"] == 1
    assert result.structured_content["tableau_release"] == "2026.2"


async def test_missing_file_is_a_tool_error_the_model_can_read(tmp_path):
    async with Client(mcp) as client:
        result = await client.call_tool("twb-status", {"path": str(tmp_path / "nope.twb")})
    assert result.is_error is True
    assert "File not found" in result.content[0].text
