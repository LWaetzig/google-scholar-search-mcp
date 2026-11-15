# google-scholar-search-mcp

An MCP (Model Context Protocol) server for searching Google Scholar, built for AI assistants and automation workflows that need papers, authors, citations, and BibTeX entries.

## Table of Contents
1. [Features](#features)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Examples](#examples)
6. [Rate Limiting](#rate-limiting)
7. [Troubleshooting](#troubleshooting)
8. [Contributing](#contributing)


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
- `Python 3.12` or later

### Recommended: uv + one-command setup

```bash
uv tool install google-scholar-search-mcp   # or: pip install google-scholar-search-mcp
google-scholar-mcp setup
```

`setup` registers the server with Claude Desktop (`claude_desktop_config.json`) and Claude Code (`claude mcp add --scope user`), plus Cursor (`~/.cursor/mcp.json`), Windsurf and Gemini CLI when installed, and downloads the agent skill into `~/.claude/skills/google-scholar-mcp/`. Existing entries in your config are preserved. Skip parts with `--no-claude-desktop`, `--no-claude-code` or `--no-skill`. Restart your client afterwards.

Try it without installing: `uvx google-scholar-search-mcp setup`.

| Command | Purpose |
|---------|---------|
| `google-scholar-mcp` / `serve` | Run the MCP server over stdio |
| `google-scholar-mcp setup` | Configure clients and install the skill |
| `google-scholar-mcp install-skill [--target T]... [--root D] [--force]` | Download the skill into every detected agent in the project (falls back to the bundled copy offline) |

`install-skill` detects which agents the current project uses and writes to each; name targets explicitly with `--target`. It never overwrites a differing file without `--force`, and only edits the marked block in shared files.

| Target | Detected by | Written to |
|--------|-------------|------------|
| `claude-user` | always | `~/.claude/skills/google-scholar-mcp/SKILL.md` |
| `claude` | `.claude/` | `.claude/skills/google-scholar-mcp/SKILL.md` |
| `cursor` | `.cursor/` | `.cursor/rules/google-scholar-mcp.mdc` |
| `windsurf` | `.windsurf/` | `.windsurf/rules/google-scholar-mcp.md` |
| `agents` (Codex, Amp, OpenCode, Jules, …) | `AGENTS.md` | pointer block in `AGENTS.md` + `.agents/skills/google-scholar-mcp/SKILL.md` |
| `gemini` | `GEMINI.md` or `.gemini/` | pointer block in `GEMINI.md` + `.agents/skills/google-scholar-mcp/SKILL.md` |

Codex stores MCP servers in TOML (`~/.codex/config.toml`), which `setup` does not edit; its skill is covered by the `agents` target.

### Build from Source

```bash
git clone https://github.com/LWaetzig/google-scholar-search-mcp.git
cd google-scholar-search-mcp
pip install -e .
```

**Note:** This server uses the [scholarly](https://scholarly.readthedocs.io/) library to access Google Scholar. Respect Google's Terms of Service and use rate limiting appropriately to avoid being blocked.


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
| `GS_SKILL_URL` | GitHub raw URL of `SKILL.md` | URL advertised to agents in the server instructions; set to an empty string to omit |

### Agent skill

The package ships [`SKILL.md`](src/google_scholar_search_mcp/skills/google-scholar-mcp/SKILL.md), which tells an agent when and how to use the tools (tool choice, rate limits, error handling). `google-scholar-mcp setup` (or `install-skill`) downloads it from `GS_SKILL_URL` into `~/.claude/skills/google-scholar-mcp/`, falling back to the bundled copy if the download fails. The server also advertises the URL in the MCP server instructions.

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
Detailed documentation about single tools can be found [here](https://lwaetzig.github.io/google-scholar-search-mcp)

### Integration with Claude Desktop

Add the server to your Claude Desktop configuration:

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Add the `google-scholar` entry under `mcpServers`:

```json
{
  "mcpServers": {
    "google-scholar": {
      "command": "google-scholar-mcp",
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
Command: google-scholar-mcp
Transport: stdio
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


## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes with clear messages
4. Push to your fork
5. Open a pull request

### Tests

```bash
poetry run pytest tests/unit                  # fast, offline
poetry run pytest tests -m "not integration"  # what CI runs
poetry run pytest tests -m integration        # live Google Scholar, slow
```

`tests/integration` drives the real server through an in-memory MCP client against live
Google Scholar and is marked `integration` automatically. If Scholar blocks your IP, those
tests skip instead of failing. They also run weekly via the *Integration tests* workflow.

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

## License

[See LICENSE file](LICENSE)
