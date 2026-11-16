"""Protocol-level checks that need no network."""

from __future__ import annotations

from mcp.client import Client

from google_scholar_search_mcp import server

from .conftest import error_text

EXPECTED_TOOLS = {
    "search_papers",
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


ID_TOOLS = {
    "get_paper_details": {"title", "scholar_id"},
    "get_citations": {"title", "scholar_id"},
    "get_bibtex": {"title", "scholar_id"},
}


async def test_lookup_tools_accept_ids_and_require_nothing() -> None:
    async with Client(server.mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    for name, params in ID_TOOLS.items():
        schema = tools[name].input_schema
        assert params <= set(schema["properties"]), name
        assert not schema.get("required"), name


async def test_missing_identifier_is_invalid_argument() -> None:
    async with Client(server.mcp) as client:
        result = await client.call_tool("get_bibtex", {})
    assert result.is_error
    assert "[INVALID_ARGUMENT]" in error_text(result)


async def test_paging_tools_expose_an_optional_offset() -> None:
    async with Client(server.mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    for name in ("search_papers", "get_citations"):
        schema = tools[name].input_schema
        assert schema["properties"]["offset"]["default"] == 0, name
        assert "offset" not in schema.get("required", []), name


async def test_offset_past_scholars_limit_is_invalid_argument() -> None:
    async with Client(server.mcp) as client:
        result = await client.call_tool("search_papers", {"query": "x", "offset": 1000})
    assert result.is_error
    assert "[INVALID_ARGUMENT]" in error_text(result)
