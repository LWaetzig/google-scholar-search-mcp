# Tools Reference

This document provides detailed API documentation for all Google Scholar MCP tools, including parameters, return formats, best practices, and real-world examples.

---

## `search_papers`

Search Google Scholar for academic papers by keyword.

**Use Cases:**
- Literature review and background research
- Finding papers on specific topics with keyword filters
- Discovering recent publications in a field
- Building a bibliography of relevant work

**Parameters:**
- `query` (string, required): Search query (supports Google Scholar syntax)
- `max_results` (integer, default: 10): Maximum results to return (1-20)
- `year_from` (integer, optional): Filter papers from this year onward
- `year_to` (integer, optional): Filter papers up to this year
- `sort_by` (string, default: `"relevance"`): Sort order: `"relevance"` or `"date"`
- `include_patents` (boolean, default: true): Include patents in results

**Returns:**
```json
{
  "query": "machine learning",
  "total_results": 10,
  "papers": [
    {
      "title": "Paper Title",
      "authors": ["Author 1", "Author 2"],
      "year": 2023,
      "abstract": "Abstract text...",
      "num_citations": 42,
      "url": "https://scholar.google.com/...",
      "pub_url": "https://example.com/paper.pdf",
      "venue": "Conference Name",
      "scholar_id": "scholar_id",
      "author_pub_id": "author_pub_id"
    }
  ]
}
```

**Query Syntax Tips:**

Use Google Scholar's search syntax to refine results:

- **Phrase search:** `"machine learning"` — exact phrase
- **Author search:** `author:"Yann LeCun"` — papers by specific author
- **Title search:** `intitle:"attention mechanisms"` — papers with title containing keywords
- **Publication filter:** `source:"Nature Machine Intelligence"` — papers from specific journal
- **Combination:** `"deep learning" author:"Yoshua Bengio" intitle:unsupervised` — combine filters

**Examples:**

1. **Find recent papers on transformers:**
   ```
   query: "transformer architecture"
   year_from: 2020
   sort_by: "date"
   max_results: 15
   ```

2. **Find highly-cited papers on neural networks:**
   ```
   query: "neural networks"
   year_from: 2010
   year_to: 2015
   max_results: 10
   # Then look for papers with high num_citations in results
   ```

3. **Search for papers by a specific author:**
   ```
   query: author:"Geoffrey Hinton"
   max_results: 20
   ```

4. **Exclude patents from results:**
   ```
   query: "reinforcement learning"
   include_patents: false
   max_results: 10
   ```

**Common Issues:**

- **Too many results:** Add `year_from` filter or use phrase search (`"exact phrase"`)
- **No results:** Try simpler keywords or remove restrictive filters
- **Low-quality results:** Sort by "date" to get recent work, or add author names
- **Patents in results:** Set `include_patents: false`

---

## `search_author`

## `search_author`

Find a Google Scholar author profile by name.

**Use Cases:**
- Find an author's academic profile and publication list
- Track researcher's h-index, i10-index, and citation counts
- Discover researcher interests and affiliations
- Build a bibliography from a researcher's work
- Get author contact information and homepage

**Parameters:**
- `name` (string, required): Author name (e.g., "Albert Einstein")
- `max_publications` (integer, default: 5): Number of publications to include (1-20)

**Returns:**
```json
{
  "name": "Albert Einstein",
  "scholar_id": "jcX8Q...",
  "affiliation": "Princeton University",
  "email_domain": "princeton.edu",
  "interests": ["Physics", "Relativity"],
  "cited_by": 125000,
  "h_index": 98,
  "i10_index": 156,
  "homepage_url": "https://example.com",
  "publications": [
    {
      "title": "On the Electrodynamics of Moving Bodies",
      "authors": ["Albert Einstein"],
      "year": 1905,
      "num_citations": 50000
    }
  ]
}
```

**Understanding Author Metrics:**

- **h_index:** Researcher has h papers with at least h citations each (measures productivity + impact)
- **i10_index:** Number of papers with at least 10 citations (measures highly-cited work)
- **cited_by:** Total citation count across all papers
- **scholar_id:** Unique Google Scholar ID (useful for direct URL: scholar.google.com/citations?user=SCHOLAR_ID)

**Examples:**

1. **Find an author and get their top 20 papers:**
   ```
   name: "Yoshua Bengio"
   max_publications: 20
   ```

2. **Discover an author's research interests:**
   ```
   name: "Fei-Fei Li"
   max_publications: 10
   # Returns interests array: ["Computer Vision", "Machine Learning", etc.]
   ```

3. **Compare authors by h-index:**
   ```
   # Search multiple authors and compare their h_index values
   # Higher h_index = more established researcher
   ```

**Tips for Better Results:**

- **Include middle initials** if available (helps with disambiguation): `"John D. Hunter"` vs `"John Hunter"`
- **Use full names** when possible; first/last alone may return multiple matches
- **Check affiliation** in results to confirm you found the right person
- **Use scholar_id** from results to create permanent links to their profile

**Common Issues:**

- **Multiple authors with same name:** Results show first match; if wrong person, try adding affiliation context in search
- **Name variations:** If search fails, try alternate spellings or initials
- **No email_domain:** Some authors haven't verified email on Google Scholar

---

## `get_paper_details`

## `get_paper_details`

Get full details of a specific paper by its title.

**Use Cases:**
- Fetch comprehensive metadata for a known paper
- Get citation trends over time (cites_per_year)
- Check if paper has public/open access version
- Retrieve BibTeX citation data
- Analyze paper's impact trajectory

**Parameters:**
- `title` (string, required): Paper title (exact or close match)

**Returns:**
```json
{
  "title": "Paper Title",
  "authors": ["Author 1"],
  "year": 2023,
  "abstract": "Abstract...",
  "num_citations": 42,
  "cites_per_year": {"2023": 10, "2024": 32},
  "public_access": true,
  "bibtex": "@article{...}",
  "url": "https://scholar.google.com/...",
  "pub_url": "https://example.com/paper.pdf",
  "venue": "Conference or Journal Name"
}
```

**Examples:**

1. **Get full details of a famous paper:**
   ```
   title: "Attention is All You Need"
   # Returns full metadata including citation trends
   ```

2. **Track citation growth over time:**
   ```
   title: "ImageNet-21k Pretraining for the Masses"
   # Use cites_per_year to plot impact over time
   ```

3. **Get BibTeX directly:**
   ```
   title: "Batch Normalization: Accelerating Deep Network Training"
   # Returns bibtex field with citation entry
   ```

**Interpreting Citation Trends:**

- **Steep growth:** Paper is gaining influence and relevance
- **Plateau:** Mature work that's foundational (well-cited but stable)
- **Recent surge:** Breakthrough paper being rediscovered or applied to new areas
- **Spike followed by drop:** Trendy topic that moved out of fashion

**Common Issues:**

- **Exact title required:** Paper titles must match closely; use exact title from paper PDF
- **Multiple versions:** If paper appears multiple times, Google Scholar returns first match
- **Very recent papers:** May not have complete citation data or may show 0 citations initially

---

## `get_citations`

## `get_citations`

Get papers that cite a given paper.

**Use Cases:**
- Forward citation tracking (see how a paper was used/extended)
- Analyze impact and adoption of a foundational work
- Find related recent research building on older work
- Discover how a method was applied in different domains
- Build a citation network map

**Parameters:**
- `title` (string, required): Title of the paper to find citations for
- `max_results` (integer, default: 10): Maximum citing papers (1-20)

**Returns:**
```json
{
  "cited_paper_title": "Original Paper Title",
  "total_citations": 342,
  "citations": [
    {
      "title": "Paper That Cites Original",
      "authors": ["Author"],
      "year": 2024,
      "num_citations": 5
    }
  ]
}
```

**Examples:**

1. **Find papers that cite a foundational method:**
   ```
   title: "Attention is All You Need"
   max_results: 20
   # Returns papers that built on transformer architecture
   ```

2. **Discover applications of a technique:**
   ```
   title: "BERT: Pre-training of Deep Bidirectional Transformers"
   max_results: 15
   # Returns papers applying BERT to NLP tasks
   ```

3. **Track influence in specific domain:**
   ```
   title: "ImageNet Large Scale Visual Recognition Challenge"
   max_results: 20
   # Returns papers using ImageNet benchmark
   ```

**Workflow: Building a Citation Network**

1. Start with a foundational paper (e.g., "ResNet")
2. Use `get_citations` to find papers citing it
3. For influential citing papers, use `get_citations` recursively
4. Build a forward-looking graph of how ideas evolved

**Common Patterns:**

- **Foundational papers:** Often have thousands of citations; limit results to get most relevant
- **Survey papers:** Usually cite many works; look at their references instead
- **Recent papers:** May have few citations initially; check again in 6-12 months
- **Domain-specific papers:** May be highly cited in niche area but low overall

**Tips:**

- **Sort results by relevance:** Results are returned by relevance to original paper
- **Check recent citations:** Recent citing papers often represent latest applications
- **Cross-reference with search_papers:** Use keywords from citing papers for deeper research

---

## `bulk_search`

## `bulk_search`

Search multiple queries sequentially with automatic rate limiting.

**Use Cases:**
- Literature reviews across multiple topics
- Batch research tasks (compare 5-10 topics)
- Survey paper research (systematically explore sub-topics)
- Benchmarking multiple search strategies
- Building comprehensive keyword research

**Parameters:**
- `queries` (array of strings, required): Search queries (maximum 10)
- `max_results_per_query` (integer, default: 5): Results per query (1-10)
- `year_from` (integer, optional): Filter papers from this year onward
- `year_to` (integer, optional): Filter papers up to this year

**Returns:**
```json
{
  "results": [
    {
      "query": "machine learning",
      "total_results": 5,
      "papers": [...]
    }
  ],
  "total_queries": 2,
  "completed_queries": 2,
  "errors": []
}
```

**Why Use bulk_search?**

- **Rate limiting:** Automatically spaces requests 5-15 seconds apart (safer than rapid searches)
- **Atomic operation:** Executes all queries in one session; better for large batch jobs
- **Error handling:** Captures errors per query without stopping the entire batch
- **Efficiency:** Intended for batch operations; don't use for single searches

**Examples:**

1. **Literature review on neural networks:**
   ```
   queries: [
     "convolutional neural networks",
     "recurrent neural networks",
     "transformer architectures",
     "attention mechanisms",
     "batch normalization"
   ]
   max_results_per_query: 5
   year_from: 2015
   ```

2. **Compare search strategies:**
   ```
   queries: [
     "deep learning",
     "machine learning",
     "artificial intelligence",
     "neural networks"
   ]
   max_results_per_query: 10
   # Returns 40 total papers across 4 related topics
   ```

3. **Systematic review by time period:**
   ```
   # First batch: foundational work
   queries: ["machine learning 1990-2000"]
   year_from: 1990
   year_to: 2000
   
   # Second batch: modern work
   queries: ["deep learning 2015-2025"]
   year_from: 2015
   ```

**Common Patterns:**

- **Narrow each query:** More specific queries return better results than broad keywords
- **Use author filters:** `author:"Yann LeCun"` can be one of your queries
- **Cross-domain searches:** Mix fundamental and applied topics for comprehensive view
- **Error analysis:** Check `errors` array for failed queries; high error rate may indicate rate-limiting

**Handling Errors:**

```json
{
  "results": [
    {"query": "Query 1", "total_results": 5, "papers": [...]},
    {"query": "Query 2", "total_results": 0, "papers": [], "message": "Error: ..."}
  ],
  "total_queries": 2,
  "completed_queries": 1,
  "errors": ["Query 2: Connection timeout"]
}
```

If errors occur:
- **Timeout errors:** Increase `GS_MAX_DELAY` or reduce batch size
- **Rate limit errors:** Increase delays and try again later
- **No results:** Check query syntax or simplify keywords

---

## `get_bibtex`

## `get_bibtex`

Get BibTeX citation entry for a paper.

**Use Cases:**
- Generate citations for papers during literature reviews
- Build bibliography files for LaTeX documents
- Export citations to reference managers (Zotero, Mendeley, etc.)
- Batch generate citations for multiple papers
- Maintain consistent citation formatting

**Parameters:**
- `title` (string, required): Paper title

**Returns:**
```
@article{einstein1905,
  title={On the Electrodynamics of Moving Bodies},
  author={Einstein, Albert},
  journal={Annalen der Physik},
  year={1905}
}
```

**Examples:**

1. **Get BibTeX for a single paper:**
   ```
   title: "ImageNet-21k Pretraining for the Masses"
   # Copy-paste result directly into .bib file
   ```

2. **Workflow: Build bibliography for literature review**
   ```
   1. Use search_papers to find relevant papers
   2. For each paper, use get_bibtex to generate citation
   3. Collect all entries into single bibliography.bib file
   4. Use in LaTeX: \bibliography{bibliography}
   ```

3. **Generate citations for all papers by an author:**
   ```
   1. Use search_author to find author and their publications
   2. For each publication, use get_bibtex
   3. Consolidate into author bibliography
   ```

**BibTeX Entry Types:**

- `@article` — Journal papers (most common)
- `@inproceedings` — Conference papers
- `@book` — Books
- `@misc` — Preprints, technical reports
- `@thesis` — PhD/Master theses

Google Scholar typically detects the correct type automatically.

**Tips:**

- **Manual editing:** Generated entries may need refinement (e.g., add DOI, fix formatting)
- **Incomplete metadata:** Some papers may have minimal BibTeX data; supplement from paper PDF
- **Multiple versions:** Different sources (conference vs journal) may have different entries
- **Unicode issues:** If using special characters, ensure .bib file is UTF-8 encoded

**Common Issues:**

- **No BibTeX returned:** Paper may not have full metadata in Google Scholar
- **Incorrect fields:** Some automated entries may have wrong information; verify against paper
- **Authors formatting:** Different systems format author names differently; ensure consistency

---

## Recommended Workflows

### Workflow 1: Quick Paper Discovery

```
1. search_papers(query="neural networks", max_results=5)
2. For interesting papers:
   - get_paper_details(title) → get full metadata
   - get_bibtex(title) → add to bibliography
```

### Workflow 2: Author Analysis

```
1. search_author(name="Yann LeCun", max_publications=20)
2. For each publication:
   - get_paper_details(title) → understand impact
   - get_citations(title) → see how work was extended
3. Track author h-index and impact over time
```

### Workflow 3: Citation Network Mapping

```
1. search_papers(query="attention mechanisms", max_results=3)
2. For each key paper:
   - get_citations(title, max_results=10) → find citing papers
   - get_citations(citing_paper) → find second-order citations
3. Build a forward citation chain: foundational → intermediate → recent work
```

### Workflow 4: Comprehensive Literature Review

```
1. bulk_search(queries=[
     "topic overview",
     "method A",
     "method B", 
     "applications",
     "recent advances"
   ], max_results_per_query=5)
2. For each result:
   - get_paper_details(title) → review abstracts and metrics
   - get_bibtex(title) → collect citations
3. Use cites_per_year to understand paper maturity
```

### Workflow 5: Finding Related Work

```
1. Start with a seminal paper: search_papers(query="exact title", max_results=1)
2. get_paper_details(title) → understand the paper
3. get_citations(title, max_results=20) → find recent work building on it
4. For each citing paper:
   - search_papers with keywords from the citation
   - Explore related domains via get_author
```

---

## Performance Considerations

| Operation | Speed | Rate Limit Impact | Best For |
|-----------|-------|-------------------|----------|
| `search_papers` | Fast | Medium | Quick keyword searches |
| `search_author` | Fast | Low | Author lookups |
| `get_paper_details` | Medium | Medium | Deep dives into specific papers |
| `get_citations` | Slow | High | Citation tracking (use sparingly) |
| `bulk_search` | Slow | High | Batch operations (use for multiple queries) |
| `get_bibtex` | Fast | Low | Citation generation |

**Optimization Tips:**

- Use `bulk_search` for multiple queries instead of repeated `search_papers` calls
- Cache results locally to avoid repeated API calls for the same paper
- Use `max_results` carefully: requesting 20 results is slower than requesting 5
- Batch citation queries: use `bulk_search` pattern for multiple papers instead of sequential calls