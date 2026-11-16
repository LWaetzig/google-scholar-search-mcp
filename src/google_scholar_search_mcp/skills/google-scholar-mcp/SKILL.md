---
name: google-scholar-mcp
description: Search Google Scholar for papers, citations and BibTeX through the google-scholar-search-mcp server. Use when the user wants to find, cite or compare academic literature, see who cites a paper, or needs a BibTeX entry. Prefer arXiv tools for arXiv-only lookups; not for general web search.
---

# Google Scholar research with google-scholar-search-mcp

Five tools, backed by the `scholarly` library scraping Google Scholar. If none
are available, tell the user the Google Scholar MCP server is not connected
instead of recalling paper details from memory. Never invent titles, authors,
citation counts or BibTeX.

## When to use it

- "Find papers on X", literature reviews, related-work sections
- Who wrote or cites a paper; citation counts; and what an author wrote
- A BibTeX entry for a known paper
- Venues beyond arXiv (journals, conferences, patents)

Do not use it for general web questions, full-text reading (it returns metadata
and abstracts/snippets only), or when an arXiv ID is already known and an arXiv
tool is available.

## Choosing a tool

| Goal | Tool |
|---|---|
| Topic or keyword search | `search_papers` |
| Several topics at once | `bulk_search` (max 10 queries) |
| Full metadata of one known paper | `get_paper_details` |
| Who cites a paper | `get_citations` |
| Citation entry | `get_bibtex` |

Typical flow: `search_papers` → `get_paper_details` for the candidates that
matter → `get_bibtex` only for papers the user will cite.

## Parameters

- `search_papers(query, max_results=10 [1-20], year_from, year_to, sort_by="relevance"|"date", include_patents=true, offset=0)`.
  Set `include_patents=false` for academic literature.
- `get_paper_details` / `get_citations(max_results=10 [1-20], offset=0)` / `get_bibtex`
  accept `scholar_id` or `title` (`scholar_id` wins).
  **Prefer IDs** copied from an earlier result: a title search takes the first
  hit, which can be a different paper, and costs an extra request. `scholar_id` comes
  from any paper result.
  With only `scholar_id`, `get_citations` omits the cited title (one request fewer).
  Fall back to the exact title from a search result when no ID is at hand.
- **Paging:** `search_papers` and `get_citations` return `offset` and
  `next_offset`. For more results, repeat the call with `offset=next_offset`;
  `null` means there are no more. Scholar serves at most the first 1000 results
  of a query, so narrow the query (years, terms) instead of paging deep. For
  further citation pages pass `scholar_id` rather than the title (saves a request).
- `bulk_search(queries, max_results_per_query=5 [1-10], year_from, year_to)`
  runs queries one after another and reports per-query errors without aborting.

Values outside the stated ranges are clamped, not rejected.

## Rate limits: this is the important part

Google Scholar blocks automated traffic. The server waits 5-15 seconds between
requests by default (every HTTP request, so a title lookup that needs a search
and a fetch waits twice), so calls are **slow** and a bulk search of 10 queries can
take minutes.

- Plan queries up front; prefer one well-chosen query over many variations.
- Use `bulk_search` for batches instead of many parallel calls.
- Keep `max_results` small (5-10). Every page is another slow request: page
  (`offset`) only when the user asks for more, never for completeness.
- Do not retry in a loop. Errors start with a stable code:
  - `[BLOCKED]` (bot check, CAPTCHA, sign-in redirect): stop, tell the user.
    The server then refuses Scholar calls for a cooldown (default 15 min), so
    retrying only returns the same error. Suggest waiting, another network, or
    fresh browser cookies (the user copies a Scholar request from their browser and
    runs `google-scholar-mcp set-cookies`; see the README) or a
    JavaScript-capable proxy (`GS_PROXY_TYPE=scraperapi`).
  - `[RATE_LIMITED]` (throttled after retries): wait before trying again.
  - `[INVALID_ARGUMENT]`: no identifier given; supply an ID or title.
  - `[NOT_FOUND]` (no match): retrying the same input will not help; use the
    exact title from a search result or simplify the query.
- Reuse results already in the conversation. The server also caches successful
  results in memory (default 1 h), so repeating a lookup is instant and free; it
  does not cache errors.

## Author profiles are not available

Google Scholar requires a Google sign-in for author profile pages, and this
server never uses a logged-in session, so there is no author tool. To learn what
an author wrote, search `search_papers` with `author:"Name"` and say that the
results are papers, not a profile (no h-index).

## Search strategy

- Use specific terms and quoted phrases; add `year_from` for recent work.
- `sort_by="date"` for "latest"; relevance otherwise.
- Highly cited results come first by relevance, so check the year before calling
  something state of the art.
- A "not found" result for a title often means a wording mismatch: search by
  keywords first, then use the title as returned.

## Presenting results

- Cite title, authors, year, venue, and citation count, and link the paper when
  a URL is returned.
- Citation counts are Google Scholar's and are approximate and change over time.
- Say when a field is missing rather than filling it in.
- BibTeX from Scholar is sometimes incomplete or oddly keyed; suggest the user
  check it before submission.
