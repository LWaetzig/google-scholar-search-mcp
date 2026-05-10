Quickstart
==========

Once the server is configured in your MCP client you can start querying Google Scholar immediately.
Below are example prompts and the tool calls they map to.

.. note::

   Google Scholar rate-limits scrapers aggressively. Delays between requests are applied
   automatically — expect a few seconds between calls. Use :ref:`bulk_search` for
   multiple queries to batch them efficiently.

----

Search by Topic
---------------

Ask your assistant:

  *"Find the most cited papers on transformer architectures for NLP."*

The assistant calls :ref:`search_papers` with:

.. code-block:: json

   {
     "query": "transformer architecture natural language processing",
     "max_results": 10,
     "sort_by": "relevance"
   }

----

Find an Author
--------------

  *"Show me Yann LeCun's Google Scholar profile."*

The assistant calls :ref:`search_author` with:

.. code-block:: json

   {
     "name": "Yann LeCun",
     "max_publications": 5
   }

----

Get Full Paper Details
----------------------

  *"Get the full details for the Attention Is All You Need paper."*

The assistant calls :ref:`get_paper_details` with:

.. code-block:: json

   {
     "title": "Attention Is All You Need"
   }

----

Find Citing Papers
------------------

  *"Which papers have cited BERT?"*

The assistant calls :ref:`get_citations` with:

.. code-block:: json

   {
     "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
     "max_results": 10
   }

----

Batch Literature Review
------------------------

  *"Search for papers on diffusion models, contrastive learning, and NeRF — give me five results each."*

The assistant calls :ref:`bulk_search` with:

.. code-block:: json

   {
     "queries": [
       "diffusion models image generation",
       "contrastive self-supervised learning",
       "neural radiance fields NeRF"
     ],
     "max_results_per_query": 5
   }

----

Export BibTeX
-------------

  *"Give me the BibTeX entry for the GPT-3 paper."*

The assistant calls :ref:`get_bibtex` with:

.. code-block:: json

   {
     "title": "Language Models are Few-Shot Learners"
   }

The tool returns a ready-to-paste BibTeX string you can drop into any ``.bib`` file.
