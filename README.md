# Idea Miner 🔍

A modern async Python CLI for mining Reddit for microSaaS and side-hustle ideas using AI.

**No Reddit API keys required!** Uses RSS feeds and public JSON endpoints.

## Features

- **No API keys needed** - Uses Reddit RSS feeds + JSON endpoints
- **Async Reddit ingestion** with `httpx` and concurrency control
- **Tenacity retries** with exponential backoff + jitter for resilience
- **LangChain structured outputs** for reliable idea extraction and scoring
- **SQLite storage** with async `aiosqlite`
- **Typer CLI** with subcommands, help, and rich output
- **Pydantic Settings** for type-safe configuration via environment variables

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

1. **RSS Feeds**: Fetches posts from `https://reddit.com/r/{subreddit}/hot.rss`
2. **JSON Comments**: Scrapes comments from `https://reddit.com/r/.../comments/{id}/.json`
3. **AI Analysis**: Uses LangChain + OpenAI to extract and score business ideas
4. **SQLite Storage**: Persists posts and scored ideas locally

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

Ideas are automatically disqualified if they are:
- Get-rich-quick or scammy
- Illegal or unsafe
- Pure labor disguised as SaaS
- "AI wrapper" with no unique value

## Project Structure

```
src/idea_miner/
├── __init__.py          # Package init
├── __main__.py          # Entry point
├── cli.py               # Typer CLI commands
├── config.py            # Pydantic Settings
├── logging_config.py    # Structlog setup
├── reddit_async.py      # RSS + JSON scraping
├── store.py             # SQLite storage
├── models.py            # Pydantic models
├── prompts.py           # LLM prompts
├── extract_async.py     # Idea extraction
├── score_async.py       # Idea scoring
├── analyze.py           # Combined analysis
├── dedupe.py            # Deduplication
└── pipeline.py          # Orchestration
```

## Rate Limiting

Reddit may rate-limit aggressive scraping. The tool includes:
- Semaphore-based concurrency control (default: 8 concurrent requests)
- 0.5s delay between comment fetches
- Tenacity retries with exponential backoff

If you see 429 errors, reduce `IDEA_MINER_MAX_CONCURRENCY` or add delays.

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
