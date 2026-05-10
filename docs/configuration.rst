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
     - Maximum pause — actual delay is random in ``[min, max]``
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
