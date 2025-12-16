# Idea Miner 🔍

A modern async Python CLI for mining Reddit for microSaaS and side-hustle ideas using AI.

**No Reddit API keys required!** Uses RSS feeds and public JSON endpoints.

## Features

- **No API keys needed** - Uses Reddit RSS feeds + JSON endpoints
- **Async Reddit ingestion** with `httpx`, connection pooling, and concurrency control  
- **Robust retries** with exponential backoff, jitter, and 429/rate-limit handling
- **LangChain structured outputs** for reliable idea extraction and scoring
- **Evidence-based scoring** with source attribution and signal types
- **SQLite storage** with async `aiosqlite`
- **Typer CLI** with subcommands, help, and rich output
- **Pydantic Settings** for type-safe configuration
- **Modular architecture** with split CLI and store packages

## Installation

```bash
# Clone the repo
cd reddit-miner

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install in editable mode
pip install -e .
```

## Configuration

Create a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` with your OpenAI API key:

```bash
# OpenAI API key (required for AI analysis)
OPENAI_API_KEY=sk-your-api-key

# Subreddits to mine (JSON array)
IDEA_MINER_SUBREDDITS=["Entrepreneur", "Startups", "SaaS", "SideProject"]

# OpenAI model
IDEA_MINER_OPENAI_MODEL=gpt-4o
```

## Usage

### Initialize Database

```bash
idea-miner init-db
```

### Run Full Pipeline

Fetch posts from Reddit and analyze with AI:

```bash
idea-miner run
```

Options:
- `-s, --subreddit`: Override subreddits to mine (can specify multiple)
- `-l, --limit`: Posts per subreddit (RSS limited to ~25)
- `-p, --process-limit`: Max posts to process with AI
- `--skip-fetch`: Only process existing unprocessed posts
- `--log-level`: DEBUG, INFO, WARNING, ERROR

Examples:

```bash
# Mine specific subreddits
idea-miner run -s Entrepreneur -s Startups -l 20

# Process only 10 posts with AI
idea-miner run -p 10

# Process existing posts without fetching new ones
idea-miner run --skip-fetch
```

### Fetch Only

Fetch Reddit posts without AI processing (builds corpus, no API costs):

```bash
idea-miner fetch -s Entrepreneur -l 25
```

### View Top Ideas

```bash
idea-miner top -l 10
```

### Show Idea Details

```bash
idea-miner show 1
```

### Generate Reports

```bash
# Markdown report
idea-miner report --run 1

# JSON report
idea-miner report --run 1 --format json
```

### View Run History

```bash
idea-miner runs
```

### Export Ideas

```bash
# Export to JSON
idea-miner export -o ideas.json

# Export to CSV
idea-miner export -o ideas.csv -l 100
```

### Database Stats

```bash
idea-miner stats
```

## How It Works

1. **RSS Feeds**: Fetches posts from `https://reddit.com/r/{subreddit}/new.rss`
2. **JSON Comments**: Scrapes comments from `https://reddit.com/r/.../comments/{id}/.json`
3. **AI Analysis**: Uses LangChain + OpenAI to extract and score business ideas
4. **Evidence Attribution**: Tracks which quotes came from posts vs comments
5. **SQLite Storage**: Persists posts and scored ideas locally

## Scoring Rubric

Ideas are scored 0-10 on five dimensions:

| Dimension | Description |
|-----------|-------------|
| **Practicality** | Build scope, dependencies, time-to-MVP |
| **Profitability** | Pricing power, margins, buyer value |
| **Distribution** | Ability to reach buyers, channel leverage |
| **Competition** | Saturation (higher if less crowded) |
| **Moat** | Data, workflow lock-in, switching costs |

**Total Score**: 0-50 (sum of all dimensions)

### Extraction States

- **extracted**: Valid idea identified and scored
- **not_extractable**: No viable idea (meta post, question only, etc.)
- **disqualified**: Idea exists but fails quality rules

### Evidence Signals

Each piece of evidence is tagged with:
- **source**: `post` or `comment`
- **signal_type**: `pain`, `willingness_to_pay`, `alternatives`, `urgency`, `repetition`, `budget`

## Project Structure

```
src/idea_miner/
├── cli/                 # CLI subcommands
│   ├── __init__.py     # App setup + version
│   ├── pipeline.py     # run command
│   ├── fetch.py        # fetch command
│   ├── ideas.py        # top, show, export
│   ├── report.py       # report, runs
│   └── db.py           # init-db, stats
├── store/               # Storage layer
│   ├── __init__.py
│   ├── schema.py       # SQL schema
│   └── core.py         # AsyncStore class
├── http_client.py       # Centralized HTTP client
├── retry_policy.py      # Retry decorators + 429 handling
├── reddit_async.py      # RSS + JSON scraping
├── models.py            # Pydantic models
├── prompts.py           # LLM prompts
├── analyze.py           # Combined extraction + scoring
├── dedupe.py            # rapidfuzz deduplication
├── pipeline.py          # Orchestration
├── report.py            # Report generation
└── config.py            # Pydantic Settings
```

## Rate Limiting

Reddit may rate-limit aggressive scraping. Built-in protections:

- **Connection pooling**: Max 20 connections, 10 keepalive
- **Semaphore concurrency**: Default 8 concurrent requests
- **Polite delays**: 0.5s between comment fetches
- **429 handling**: Respects `Retry-After` header
- **Tenacity retries**: Exponential backoff with jitter

If you see 429 errors, reduce `IDEA_MINER_MAX_CONCURRENCY` in your `.env`.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run linting
ruff check src/

# Run tests
pytest
```

## License

MIT
