.. _bulk_search:

bulk_search
===========

Search Google Scholar for multiple queries sequentially with automatic rate limiting.

Use this tool for batch literature reviews when you need results for several
topics at once. Each query runs one at a time with randomised delays between
them to avoid triggering Google Scholar's bot detection. Partial failures are
captured per-query so a single bad result does not abort the whole batch.

Parameters
----------

.. list-table::
   :header-rows: 1
   :widths: 28 12 12 48

   * - Parameter
     - Type
     - Default
     - Description
   * - ``queries``
     - ``list[str]``
     - *(required)*
     - List of search queries. Maximum 10 queries per call.
   * - ``max_results_per_query``
     - ``int``
     - ``5``
     - Results to return for each query. Clamped to 1–10.
   * - ``year_from``
     - ``int``
     - ``None``
     - Filter to papers published in or after this year (applied to all queries).
   * - ``year_to``
     - ``int``
     - ``None``
     - Filter to papers published in or before this year (applied to all queries).

Return Value
------------

Returns a :class:`~google_scholar_search_mcp.models.BulkSearchResponse` containing:

- ``results`` — list of :class:`~google_scholar_search_mcp.models.SearchResponse`, one per query
- ``total_queries`` — number of queries submitted
- ``completed_queries`` — number of queries that succeeded
- ``errors`` — list of error strings for any failed queries

Examples
--------

**Multi-topic literature sweep:**

.. code-block:: json

   {
     "queries": [
       "diffusion models image generation",
       "contrastive self-supervised learning",
       "neural radiance fields NeRF"
     ],
     "max_results_per_query": 5
   }

**Year-filtered batch search:**

.. code-block:: json

   {
     "queries": [
       "large language model alignment",
       "reinforcement learning from human feedback"
     ],
     "max_results_per_query": 8,
     "year_from": 2022
   }

.. warning::

   Even with rate limiting, large batches (10 queries) can take several minutes.
   Prefer smaller batches or lower ``max_results_per_query`` when low latency matters.
