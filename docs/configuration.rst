Configuration
=============

The server is configured via the :class:`~google_scholar_search_mcp.config.Config` dataclass,
which is instantiated once at module level by reading environment variables through
:meth:`~google_scholar_search_mcp.config.Config.from_env`.
No configuration files are required — all settings have sensible defaults.

See the full class reference at :class:`google_scholar_search_mcp.config.Config`.

----

Defaults
--------

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Field
     - Default value
     - Notes
   * - ``min_delay_seconds``
     - ``5.0``
     - Minimum pause between Scholar requests (seconds)
   * - ``max_delay_seconds``
     - ``15.0``
     - Maximum pause — actual delay is random in ``[min, max]``, applied between every HTTP request to Scholar (a tool call making several requests waits several times)
   * - ``max_retries``
     - ``3``
     - Retry attempts on rate-limit errors before raising
   * - ``proxy_type``
     - ``NONE``
     - Proxy mode: ``NONE`` · ``FREE`` · ``SINGLE`` · ``SCRAPERAPI``
   * - ``proxy_http``
     - *(unset)*
     - HTTP proxy URL, used when ``proxy_type`` is ``SINGLE``
   * - ``proxy_https``
     - *(unset)*
     - HTTPS proxy URL, used when ``proxy_type`` is ``SINGLE``
   * - ``scraperapi_key``
     - *(unset)*
     - API key for ScraperAPI, used when ``proxy_type`` is ``SCRAPERAPI``
   * - ``timeout_seconds``
     - ``30``
     - Scholarly request timeout in seconds

----

Environment Variables
---------------------

All fields are populated from environment variables:

.. list-table::
   :header-rows: 1
   :widths: 30 25 45

   * - Environment variable
     - Field
     - Example
   * - ``GS_MIN_DELAY``
     - ``min_delay_seconds``
     - ``GS_MIN_DELAY=3.0``
   * - ``GS_MAX_DELAY``
     - ``max_delay_seconds``
     - ``GS_MAX_DELAY=10.0``
   * - ``GS_MAX_RETRIES``
     - ``max_retries``
     - ``GS_MAX_RETRIES=5``
   * - ``GS_PROXY_TYPE``
     - ``proxy_type``
     - ``GS_PROXY_TYPE=scraperapi``
   * - ``GS_PROXY_HTTP``
     - ``proxy_http``
     - ``GS_PROXY_HTTP=http://proxy:8080``
   * - ``GS_PROXY_HTTPS``
     - ``proxy_https``
     - ``GS_PROXY_HTTPS=https://proxy:8080``
   * - ``GS_SCRAPERAPI_KEY``
     - ``scraperapi_key``
     - ``GS_SCRAPERAPI_KEY=abc123``
   * - ``GS_TIMEOUT``
     - ``timeout_seconds``
     - ``GS_TIMEOUT=60``
   * - ``GS_COOKIES_FILE``
     - ``cookies``
     - ``GS_COOKIES_FILE=~/.google-scholar-cookies``
   * - ``GS_COOKIES``
     - ``cookies``
     - ``GS_COOKIES='NID=...; GSP=...'``
   * - ``GS_USER_AGENT``
     - ``user_agent``
     - ``GS_USER_AGENT='Mozilla/5.0 ...'``
   * - ``GS_BLOCK_COOLDOWN``
     - ``block_cooldown_seconds``
     - ``GS_BLOCK_COOLDOWN=900``
   * - ``GS_CACHE_TTL``
     - ``cache_ttl_seconds``
     - ``GS_CACHE_TTL=3600`` (``0`` disables)
   * - ``GS_CACHE_SIZE``
     - ``cache_max_entries``
     - ``GS_CACHE_SIZE=256``

----

Browser Cookies (experimental)
------------------------------

Scholar's bot check needs JavaScript. Cookies (and the matching User-Agent) from
a browser that already passed it can be supplied with ``GS_COOKIES_FILE`` (or
``GS_COOKIES``) and ``GS_USER_AGENT``; they are sent with every Scholar request.
Use a private window where you are **not logged in**, on the same machine and
network as the server, and expect to renew them when they expire. Cookie values
are never logged or printed. Verify with ``google-scholar-mcp doctor``; see the
README for the step-by-step.

``google-scholar-mcp set-cookies`` saves them for you: copy the Scholar request
in the browser's developer tools (*Copy as cURL* or *Copy request headers*) and
run the command. It writes cookies and User-Agent to
``~/.config/google-scholar-mcp/cookies``, which the server reads automatically
when neither ``GS_COOKIES_FILE`` nor ``GS_COOKIES`` is set.

----

Proxy Modes
-----------

``NONE``
   No proxy — connects to Google Scholar directly. Suitable for light usage.

``FREE``
   Uses the scholarly library's built-in free proxy rotation. May be unreliable.

``SINGLE``
   Routes all requests through a specific proxy defined by ``GS_PROXY_HTTP`` / ``GS_PROXY_HTTPS``.

``SCRAPERAPI``
   Uses `ScraperAPI <https://www.scraperapi.com>`_ for reliable access. Requires ``GS_SCRAPERAPI_KEY``.

----

Agent Skill
-----------

The repository ships ``src/google_scholar_search_mcp/skills/google-scholar-mcp/SKILL.md``, which explains to an
agent when and how to use the tools (tool choice, rate limits, error handling).
The server appends the skill's URL (``GS_SKILL_URL``) to its MCP instructions,
which clients show to the agent on connect. Run ``google-scholar-mcp setup`` (or
``google-scholar-mcp install-skill``) to download it into
``~/.claude/skills/google-scholar-mcp/``; if the download fails the bundled
copy is used.

----

Passing Config via Claude Desktop
----------------------------------

Set environment variables in the MCP server entry:

.. code-block:: json

   {
     "mcpServers": {
       "google-scholar": {
         "command": "google-scholar-mcp",
         "env": {
           "GS_MIN_DELAY": "3.0",
           "GS_MAX_DELAY": "8.0",
           "GS_PROXY_TYPE": "scraperapi",
           "GS_SCRAPERAPI_KEY": "your-key-here"
         }
       }
     }
   }

Extending Config
----------------

``Config`` is a frozen dataclass. To override defaults programmatically,
instantiate it directly in a custom server entry point:

.. code-block:: python

   from google_scholar_search_mcp.config import Config, ProxyType
   from google_scholar_search_mcp import server

   server.config = Config(
       min_delay_seconds=2.0,
       max_delay_seconds=6.0,
       max_retries=5,
       proxy_type=ProxyType.SCRAPERAPI,
       proxy_http=None,
       proxy_https=None,
       scraperapi_key="your-key-here",
       timeout_seconds=60,
   )
