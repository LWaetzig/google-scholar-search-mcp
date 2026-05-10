.. _search_author:

search_author
=============

Find a Google Scholar author profile by name.

Returns the author's affiliation, h-index, i10-index, research interests,
and a sample of their publications.

Parameters
----------

.. list-table::
   :header-rows: 1
   :widths: 22 12 12 54

   * - Parameter
     - Type
     - Default
     - Description
   * - ``name``
     - ``str``
     - *(required)*
     - Author name to search for (e.g. ``"Albert Einstein"``).
   * - ``max_publications``
     - ``int``
     - ``5``
     - Number of publications to include in the profile. Clamped to 1–20.

Return Value
------------

Returns an :class:`~google_scholar_search_mcp.models.AuthorResult` containing:

- ``name`` — author's display name
- ``scholar_id`` — Google Scholar profile ID
- ``affiliation`` — institutional affiliation
- ``h_index`` — h-index
- ``i10_index`` — i10-index
- ``interests`` — list of research interest keywords
- ``publications`` — list of :class:`~google_scholar_search_mcp.models.PaperResult` objects

Examples
--------

**Find a researcher by name:**

.. code-block:: json

   {
     "name": "Geoffrey Hinton",
     "max_publications": 5
   }

**Retrieve more publications:**

.. code-block:: json

   {
     "name": "Yoshua Bengio",
     "max_publications": 15
   }

.. note::

   If multiple authors share the same name, Google Scholar returns the most
   prominent match. Use the ``scholar_id`` from the result to distinguish
   between profiles in follow-up requests.
