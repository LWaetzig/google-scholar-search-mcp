"""Errors surfaced to MCP clients.

All errors subclass :class:`~mcp.server.mcpserver.exceptions.ToolError`, so the
client receives the message as an ``isError`` tool result instead of a generic
"Error executing tool" wrapper. Every message starts with a stable ``[CODE]``
so agents can branch on it without parsing prose.
"""

from __future__ import annotations

from mcp.server.mcpserver.exceptions import ToolError


class ScholarError(ToolError):
    """Base class for errors raised by this server.

    Attributes:
        code (str): Stable machine-readable error code.
        detail (str): The message without the ``[CODE]`` prefix.
    """

    code = "ERROR"

    def __init__(self, message: str) -> None:
        """Create the error with a ``[CODE]`` prefix.

        Args:
            message (str): Human-readable explanation, including what to do next.
        """
        self.detail = message
        super().__init__(f"[{self.code}] {message}")


class ScholarNotFoundError(ScholarError):
    """Nothing on Google Scholar matched the request. Retrying will not help."""

    code = "NOT_FOUND"


class ScholarRateLimitError(ScholarError):
    """Google Scholar throttled the request (HTTP 429). Retry later."""

    code = "RATE_LIMITED"


class ScholarBlockedError(ScholarRateLimitError):
    """Google Scholar blocks the client (CAPTCHA / max tries). Stop and tell the user."""

    code = "BLOCKED"


class ScholarInvalidArgumentError(ScholarError):
    """The tool arguments are unusable (e.g. no identifier given). Fix the call."""

    code = "INVALID_ARGUMENT"
