.. _get_paper_details:

get_paper_details
=================

Get full details of a specific paper by its title.

Unlike :ref:`search_papers`, which returns lightweight results, this tool
fetches the complete record from Google Scholar including citation-per-year
statistics and the BibTeX entry.

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
     - The exact (or close) title of the paper. Google Scholar performs a
       search and fills the first match.

Return Value
------------

Returns a :class:`~google_scholar_search_mcp.models.PaperDetails` object, which extends
:class:`~google_scholar_search_mcp.models.PaperResult` with:

- ``cites_per_year`` — dict mapping year (``str``) to citation count (``int``)
- ``bibtex`` — BibTeX citation string (may be empty if unavailable)

Plus all ``PaperResult`` fields:

- ``title``, ``authors``, ``year``, ``abstract``
- ``citation_count``, ``pdf_url``, ``pub_url``

Examples
--------

**Look up a well-known paper:**

.. code-block:: json

   {
     "title": "Attention Is All You Need"
   }

**Retrieve citation trend data:**

.. code-block:: json

   {
     "title": "Deep Residual Learning for Image Recognition"
   }

.. tip::

   Use :ref:`search_papers` first to confirm the exact title as it appears on
   Google Scholar, then call this tool for the complete record.
