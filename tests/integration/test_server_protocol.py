"""Protocol-level checks that need no network."""

from __future__ import annotations

from mcp.client import Client

from google_scholar_search_mcp import server

EXPECTED_TOOLS = {
    "search_papers",
    "search_author",
    "get_paper_details",
    "get_citations",
    "bulk_search",
    "get_bibtex",
}


async def test_lists_all_tools() -> None:
    async with Client(server.mcp) as client:
        tools = await client.list_tools()
    assert {t.name for t in tools.tools} == EXPECTED_TOOLS


async def test_every_tool_has_a_description_and_schema() -> None:
    async with Client(server.mcp) as client:
        tools = (await client.list_tools()).tools
    for tool in tools:
        assert tool.description, tool.name
        assert tool.input_schema["type"] == "object", tool.name
