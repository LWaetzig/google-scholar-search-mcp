.. _get_citations:

get_citations
=============

Get papers that cite a given paper.

Useful for forward-citation analysis — discovering how a foundational paper
has influenced subsequent research.

Parameters
----------

.. list-table::
   :header-rows: 1
   :widths: 22 12 12 54

   * - Parameter
     - Type
     - Default
     - Description
   * - ``title``
     - ``str``
     - *(required)*
     - Title of the paper whose citations to retrieve.
   * - ``max_results``
     - ``int``
     - ``10``
     - Maximum number of citing papers to return. Clamped to 1–20.

Return Value
------------

Returns a :class:`~google_scholar_search_mcp.models.CitationResponse` containing:

- ``cited_paper_title`` — resolved title of the source paper
- ``total_citations`` — total citation count as reported by Google Scholar
- ``citations`` — list of :class:`~google_scholar_search_mcp.models.PaperResult` objects (the citing papers)

Examples
--------

**Find papers that cite a seminal work:**

.. code-block:: json

   {
     "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
     "max_results": 10
   }

**Narrow citation list:**

.. code-block:: json

   {
     "title": "Generative Adversarial Nets",
     "max_results": 5
   }

.. note::

   ``total_citations`` reflects Google Scholar's full count; ``citations`` returns
   only the first ``max_results`` entries from that list.
