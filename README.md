# Google Scholar MCP

An MCP (Model Context Protocol) server for searching Google Scholar—papers, authors, citations, and BibTeX entries. Designed to integrate into AI assistants (Claude, etc.) with academic literature search.

## Features

- **Paper Search**: Query Google Scholar by keyword with filtering, sorting, and pagination
- **Author Lookup**: Find researcher profiles with publication lists and h-index metrics
- **Citation Tracking**: Retrieve papers that cite a given work
- **Paper Details**: Get full metadata, citations-per-year graphs, and public access info
- **BibTeX Export**: Generate citation entries in BibTeX format
- **Bulk Search**: Batch search multiple queries with automatic rate limiting
- **Rate Limiting**: Built-in delays between requests to avoid being blocked
- **Proxy Support**: Optional proxy configuration (free, single, or ScraperAPI)

## Installation

### Requirements

- Python 3.11 or later
- Dependencies: `mcp[cli]>=1.4.0`, `scholarly>=1.7.11`, `pydantic>=2.0`

### From Source

```bash
git clone https://github.com/yourusername/google-scholar-mcp.git
cd google-scholar-mcp
pip install -e .
```

## Configuration

Configure the MCP server via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GS_MIN_DELAY` | `5.0` | Minimum seconds between requests |
| `GS_MAX_DELAY` | `15.0` | Maximum seconds between requests |
| `GS_MAX_RETRIES` | `3` | Number of retries on failure |
| `GS_PROXY_TYPE` | `none` | Proxy mode: `none`, `free`, `single`, `scraperapi` |
| `GS_PROXY_HTTP` | — | HTTP proxy URL (for `single` mode) |
| `GS_PROXY_HTTPS` | — | HTTPS proxy URL (for `single` mode) |
| `GS_SCRAPERAPI_KEY` | — | ScraperAPI key (for `scraperapi` mode) |
| `GS_TIMEOUT` | `30` | Request timeout in seconds |

### Proxy Configuration Examples

**No Proxy (Default)**
```bash
export GS_PROXY_TYPE=none
```

**Free Proxy**
```bash
export GS_PROXY_TYPE=free
```

**Single Proxy**
```bash
export GS_PROXY_TYPE=single
export GS_PROXY_HTTP=http://proxy.example.com:8080
export GS_PROXY_HTTPS=https://proxy.example.com:8080
```

**ScraperAPI**
```bash
export GS_PROXY_TYPE=scraperapi
export GS_SCRAPERAPI_KEY=your_key_here
```

## Usage

### Running the Server

```bash
# Start the MCP server (communicates via stdio)
google-scholar-mcp
```

### Integration with Claude Desktop

Add the server to your Claude Desktop configuration:

**On macOS/Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "google-scholar": {
      "command": "python",
      "args": ["-m", "google_scholar_mcp.server"],
      "env": {
        "GS_MIN_DELAY": "5.0",
        "GS_MAX_DELAY": "15.0",
        "GS_PROXY_TYPE": "none"
      }
    }
  }
}
```

**On Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "google-scholar": {
      "command": "python",
      "args": ["-m", "google_scholar_mcp.server"],
      "env": {
        "GS_MIN_DELAY": "5.0",
        "GS_MAX_DELAY": "15.0",
        "GS_PROXY_TYPE": "none"
      }
    }
  }
}
```

After updating the config, restart Claude Desktop. The Google Scholar tools will appear in the MCP Tools panel.

### Integration with Other MCP Clients

Any MCP client (e.g., Cline, Continue, or custom tools) can use this server. Configure the connection to:

```
Command: python -m google_scholar_mcp.server
Transport: stdio
```

## Examples

### Example 1: Search for Recent Papers in Machine Learning

**Query:** "Find 5 papers on deep learning from 2023-2024"

**Claude Request:**
```
Using the search_papers tool, find papers on "deep learning" published between 2023 and 2024, 
sorted by relevance, limiting to 5 results.
```

### Example 2: Find an Author and Their Work

**Query:** "Find papers by Yann LeCun"

**Claude Request:**
```
Use search_author to find the scholar profile for "Yann LeCun" and show me their top 10 publications.
```

### Example 3: Citation Chain Analysis

**Query:** "What papers cite 'Attention is All You Need'?"

**Claude Request:**
```
Use get_citations to find papers that cite "Attention is All You Need" and show me the top 5.
```

### Example 4: Literature Review

**Query:** "Search for papers on: reinforcement learning, deep Q-learning, policy gradients"

**Claude Request:**
```
Use bulk_search with queries ["reinforcement learning", "deep Q-learning", "policy gradients"],
returning 5 papers per query to help me build a literature review.
```

### Example 5: Get BibTeX for Citation Management

**Query:** "Get BibTeX for 'ImageNet-21k Pretraining for the Masses'"

**Claude Request:**
```
Use get_bibtex to get the citation entry for "ImageNet-21k Pretraining for the Masses" 
so I can add it to my bibliography.
```

## Rate Limiting

The server automatically enforces rate limiting between requests to avoid overloading Google Scholar's servers:

- **Min Delay** (default 5s): Minimum wait between consecutive requests
- **Max Delay** (default 15s): Maximum wait (randomized to avoid patterns)
- **Max Retries** (default 3): Retry failed requests up to this many times

These settings help prevent being blocked by Google Scholar. Adjust via environment variables if needed:

```bash
export GS_MIN_DELAY=3.0
export GS_MAX_DELAY=10.0
export GS_MAX_RETRIES=5
```

### ⚠️ IP Blocking Warning

If you exceed Google Scholar's rate limits despite the rate limiter:

- **Your IP may be temporarily blocked** (usually 24-48 hours)
- **All requests will fail** with connection errors or 429 responses
- **Blocked IPs cannot make requests** even with valid proxies on the same IP range
- **Repeated violations may trigger permanent blocks** or require CAPTCHA solving

**Recommended Practices:**

1. **Never decrease delays below 5 seconds** — the defaults are tuned for reliability
2. **Use the bulk_search tool** instead of rapid sequential searches — it includes built-in delays
3. **Add extra buffer during bulk operations** — consider setting `GS_MIN_DELAY=10.0` for large jobs
4. **Use a proxy service** (free proxy or ScraperAPI) to distribute requests across multiple IPs
5. **Monitor for 429 errors** — if you see them, increase delays immediately and wait before retrying
6. **Spread requests over time** — don't run 100 queries in 5 minutes, even with delays

### Recovery from IP Blocks

If your IP gets blocked:

- **Wait 24-48 hours** for the temporary block to expire
- **Use a proxy** — enable `GS_PROXY_TYPE=free` or `scraperapi` to route through different IPs
- **Change your network** — use a different WiFi/ISP temporarily if possible
- **Contact support** — for persistent blocks, escalate to Google Scholar support

### Choosing Appropriate Delays

| Scenario | GS_MIN_DELAY | GS_MAX_DELAY | Notes |
|----------|--------------|--------------|-------|
| **Single searches** | 5.0 | 15.0 | Default; safe for occasional queries |
| **Bulk operations** | 10.0 | 20.0 | Use for batch jobs; prevents rapid-fire requests |
| **Heavy load** | 15.0 | 30.0 | Use with proxy for large-scale research |
| **Aggressive** ⚠️ | <5.0 | <10.0 | Not recommended; high risk of IP blocking |

## Troubleshooting

### "Error: 429 Too Many Requests"

You've hit Google Scholar's rate limit. Solutions:

1. **Increase delays:** Set higher `GS_MIN_DELAY` and `GS_MAX_DELAY`
2. **Use a proxy:** Set `GS_PROXY_TYPE=free` or use ScraperAPI
3. **Wait and retry:** Google Scholar may be temporarily blocking; try again later

### "No results found"

- Check your query syntax (Google Scholar supports advanced search operators)
- Ensure the author/paper name is spelled correctly
- Try a simpler query with fewer keywords

### "Connection timeout"

- Increase `GS_TIMEOUT` if your network is slow
- Check your internet connection
- Verify proxy settings if using a proxy


## License

[See LICENSE file](LICENSE)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes with clear messages
4. Push to your fork
5. Open a pull request

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Note:** This server uses the [scholarly](https://scholarly.readthedocs.io/) library to access Google Scholar. Respect Google's Terms of Service and use rate limiting appropriately to avoid being blocked.
