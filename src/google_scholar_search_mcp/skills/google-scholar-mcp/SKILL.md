---
name: google-scholar-mcp
description: Search Google Scholar for papers, author profiles, citations and BibTeX through the google-scholar-search-mcp server. Use when the user wants to find, cite or compare academic literature, look up a researcher, see who cites a paper, or needs a BibTeX entry. Prefer arXiv tools for arXiv-only lookups; not for general web search.
---

# Google Scholar research with google-scholar-search-mcp

Seven tools, backed by the `scholarly` library scraping Google Scholar. If none
are available, tell the user the Google Scholar MCP server is not connected
instead of recalling paper details from memory. Never invent titles, authors,
citation counts or BibTeX.

## When to use it

- "Find papers on X", literature reviews, related-work sections
- Who wrote or cites a paper; citation counts; an author's h-index and works
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
| Author profile and top works | `search_author` |
| Citation entry | `get_bibtex` |

Typical flow: `search_papers` → `get_paper_details` for the candidates that
matter → `get_bibtex` only for papers the user will cite.

## Parameters

- `search_papers(query, max_results=10 [1-20], year_from, year_to, sort_by="relevance"|"date", include_patents=true)`.
  Set `include_patents=false` for academic literature.
- `search_author(name, max_publications=5 [1-20])`: use the full name; names are
  ambiguous, so check affiliation and interests before trusting a match.
- `get_paper_details(title)` / `get_citations(title, max_results=10 [1-20])` /
  `get_bibtex(title)` take the title, not an ID. Use the exact title from a
  previous search result.
- `bulk_search(queries, max_results_per_query=5 [1-10], year_from, year_to)`
  runs queries one after another and reports per-query errors without aborting.

Values outside the stated ranges are clamped, not rejected.

## Rate limits: this is the important part

Google Scholar blocks automated traffic. The server waits 5-15 seconds between
requests by default, so calls are **slow** and a bulk search of 10 queries can
take minutes.

- Plan queries up front; prefer one well-chosen query over many variations.
- Use `bulk_search` for batches instead of many parallel calls.
- Keep `max_results` small (5-10) and do not page for completeness unless asked.
- Do not retry in a loop. Errors start with a stable code:
  - `[BLOCKED]` (CAPTCHA / max tries): stop, tell the user, and suggest
    increasing `GS_MIN_DELAY` or configuring a proxy (`GS_PROXY_TYPE`).
  - `[RATE_LIMITED]` (throttled after retries): wait before trying again.
  - `[NOT_FOUND]` (no match): retrying the same input will not help; use the
    exact title from a search result or simplify the query.
- Reuse results already in the conversation.

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
