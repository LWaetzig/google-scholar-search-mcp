Installation
============

Prerequisites
-------------

- **Python 3.12** or later
- An MCP-compatible client (Claude Desktop, Cline, Continue, or any custom client)

Recommended: uv and one-command setup
-------------------------------------

.. code-block:: bash

   uv tool install google-scholar-search-mcp
   google-scholar-mcp setup

``setup`` registers the server with Claude Desktop, Claude Code, Cursor,
Windsurf and Gemini CLI (whichever are installed) and installs the agent
skill. Other servers in those configs are preserved, and existing ``env``
settings of this server are kept. Useful options:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Command
     - What it does
   * - ``google-scholar-mcp setup --no-skill``
     - Register clients only
   * - ``google-scholar-mcp install-skill``
     - Install only the skill into the agents detected in the current project
   * - ``google-scholar-mcp install-skill --target cursor``
     - Install for one agent (repeatable; see ``--help`` for names)
   * - ``--force``
     - Overwrite a skill file that differs from the current one

Without ``--force`` an existing, differing skill is never overwritten. Codex
uses a TOML config, which is not edited; add the server there by hand.

Try it without installing: ``uvx google-scholar-search-mcp setup``. Note that
this registers a temporary path, so use ``uv tool install`` for a lasting setup.

Install from PyPI
-----------------

.. code-block:: bash

   pip install google-scholar-search-mcp

Install with Poetry (recommended)
----------------------------------

.. code-block:: bash

   poetry add google-scholar-search-mcp

Build from Source
-----------------

.. code-block:: bash

   git clone https://github.com/LWaetzig/google-scholar-search-mcp.git
   cd google-scholar-search-mcp
   pip install -e .

----

MCP Client Setup
----------------

Claude Desktop
~~~~~~~~~~~~~~

Add the server entry to your Claude Desktop configuration file:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Platform
     - Path
   * - macOS
     - ``~/Library/Application Support/Claude/claude_desktop_config.json``
   * - Windows
     - ``%APPDATA%\Claude\claude_desktop_config.json``

.. code-block:: json

   {
     "mcpServers": {
       "google-scholar": {
         "command": "google-scholar-mcp"
       }
     }
   }

Restart Claude Desktop. The Google Scholar tools appear in the tool picker automatically.

.. note::

   If you installed with Poetry, use ``"command": "poetry"`` and
   ``"args": ["run", "google-scholar-mcp"]`` instead.

Other MCP Clients
~~~~~~~~~~~~~~~~~

Any MCP client that supports stdio transport can connect to this server:

.. code-block:: text

   Command:   google-scholar-mcp
   Transport: stdio

----

Building the Docs
-----------------

.. code-block:: bash

   pip install "google-scholar-search-mcp[docs]"
   # or: poetry install --with docs
   cd docs
   make html
   open _build/html/index.html
