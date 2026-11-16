.. _search_papers:

search_papers
=============

Search Google Scholar for academic papers by keyword.

Parameters
----------

.. list-table::
   :header-rows: 1
   :widths: 22 12 12 54

   * - Parameter
     - Type
     - Default
     - Description
   * - ``query``
     - ``str``
     - *(required)*
     - Search query, using the same syntax as the Google Scholar search box.
   * - ``max_results``
     - ``int``
     - ``10``
     - Maximum number of results to return. Clamped to the range 1–20.
   * - ``year_from``
     - ``int``
     - ``None``
     - Filter to papers published in or after this year.
   * - ``year_to``
     - ``int``
     - ``None``
     - Filter to papers published in or before this year.
   * - ``sort_by``
     - ``str``
     - ``"relevance"``
     - Sort order: ``"relevance"`` or ``"date"``.
   * - ``include_patents``
     - ``bool``
     - ``True``
     - Whether to include patents in the results.
   * - ``offset``
     - ``int``
     - ``0``
     - Number of results to skip, for paging. Pass the ``next_offset`` of the
       previous response. Scholar serves at most the first 1000 results of a
       query; reaching past that fails with ``[INVALID_ARGUMENT]``.

Return Value
------------

Returns a :class:`~google_scholar_search_mcp.models.SearchResponse` containing:

- ``query`` — the original query string
- ``total_results`` — number of results returned
- ``papers`` — list of :class:`~google_scholar_search_mcp.models.PaperResult` objects
- ``offset`` — the offset this page starts at
- ``next_offset`` — offset of the next page, or ``null`` when there are no more
  results (the page came back short, or Scholar's 1000-result limit is reached)

Paging
------

Call the tool again with the same arguments and ``offset`` set to
``next_offset``. Every page is at least one slow request to Google Scholar, so
page only when more results are really needed; narrowing the query (years,
more specific terms) is usually better than reading deep into a result list.

Examples
--------

**Basic keyword search:**

.. code-block:: json

   {
     "query": "large language models instruction tuning",
     "max_results": 10
   }

**Filter by year range:**

.. code-block:: json

   {
     "query": "graph neural networks",
     "max_results": 5,
     "year_from": 2021,
     "year_to": 2024
   }

**Sort by date, exclude patents:**

.. code-block:: json

   {
     "query": "protein structure prediction AlphaFold",
     "sort_by": "date",
     "include_patents": false
   }
