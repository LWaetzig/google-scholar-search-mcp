Installation
============

Prerequisites
-------------

- **Python 3.12** or later
- An MCP-compatible client (Claude Desktop, Cline, Continue, or any custom client)

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

   git clone https://github.com/LWaetzig/google-scholar-mcp.git
   cd google-scholar-mcp
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
