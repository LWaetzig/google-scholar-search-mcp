google-scholar-search-mcp
=========================

An MCP (Model Context Protocol) server that gives AI assistants direct access to `Google Scholar <https://scholar.google.com>`_.
Search papers, retrieve author profiles, explore citation networks, and export BibTeX — all from any MCP-compatible client.

.. code-block:: json

   {
     "mcpServers": {
       "google-scholar": {
         "command": "google-scholar-mcp"
       }
     }
   }

----

.. rubric:: Available Tools

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Tool
     - What it does
   * - :ref:`search_papers`
     - Keyword search with year filters and sort options
   * - :ref:`search_author`
     - Find a Google Scholar author profile by name
   * - :ref:`get_paper_details`
     - Full metadata for a specific paper by title
   * - :ref:`get_citations`
     - Papers that cite a given paper
   * - :ref:`bulk_search`
     - Batch multiple queries with automatic rate limiting
   * - :ref:`get_bibtex`
     - BibTeX citation entry for a paper

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: Tool Reference

   tools/index

.. toctree::
   :maxdepth: 1
   :caption: Configuration

   configuration

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/index
