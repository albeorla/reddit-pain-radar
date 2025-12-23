# Pain Radar 🎯

[![CI](https://github.com/albeorla/reddit-miner/actions/workflows/ci.yml/badge.svg)](https://github.com/albeorla/reddit-miner/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/albeorla/reddit-miner/branch/main/graph/badge.svg?token=YOUR_TOKEN_HERE)](https://codecov.io/gh/albeorla/reddit-miner)

**A signal tool that finds repeated pain points on Reddit and groups them into weekly "Pain Clusters" with quotes and links.**

No scraping private data. No auto-outreach. Cites sources. Filters self-promo.

![Pain Radar CLI Demo](examples/demo.gif)

## What It Does

Pain Radar tracks what Redditors are struggling with and groups similar frustrations into actionable clusters. Use it to:

- **Generate weekly digests** of the top pain points in any subreddit
- **Find patterns** across posts that point to the same unmet need
- **Build credibility** by posting genuinely useful content
- **Track signals** for specific topics or keywords

## Installation

```bash
# Clone the repo
git clone https://github.com/albeorla/reddit-miner
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
# OpenAI API key (required)
OPENAI_API_KEY=sk-your-api-key

# OpenAI model
PAIN_RADAR_OPENAI_MODEL=gpt-4o
```

## Quick Start

### 1. Initialize Database

```bash
pain-radar init-db
```

### 2. Choose Your ICP (Source Set)

```bash
# See available presets
pain-radar sources

# Add a preset that matches your target audience
pain-radar sources-add indie_saas    # Indie SaaS builders
pain-radar sources-add shopify       # Shopify merchants
pain-radar sources-add marketing     # Marketing operators
```

### 3. Fetch Reddit Posts

```bash
pain-radar fetch                     # Fetches from all active source sets
pain-radar fetch --source-set 1      # Fetch from specific source set
pain-radar fetch -s SideProject -l 5 # Override with specific subreddits
```

### 4. Analyze Posts for Pain Signals

```bash
pain-radar run -p 20                 # Analyze up to 20 posts
```

### 5. Generate Weekly Digest

```bash
pain-radar digest SideProject --top 7
```

This outputs a Reddit-ready post with:
- Top 7 pain clusters
- Verbatim quotes from real users
- Links to source threads
- Soft opt-in CTA

## Core Commands

### `pain-radar fetch`

Fetch posts from Reddit without processing (builds corpus, no API costs):

```bash
pain-radar fetch -s Entrepreneur -l 25
```

### `pain-radar run`

Fetch and analyze posts for pain signals:

```bash
pain-radar run -s SideProject -s IndieHackers -l 20 -p 15
```

Options:
- `-s, --subreddit`: Subreddits to track (can specify multiple)
- `-l, --limit`: Posts per subreddit
- `-p, --process-limit`: Max posts to analyze with AI
- `--skip-fetch`: Only process existing unprocessed posts

### `pain-radar cluster`

Group pain signals into thematic clusters:

```bash
pain-radar cluster --days 7 -s SideProject
```

### `pain-radar digest`

Generate a weekly digest for a subreddit:

```bash
# Reddit post format (default)
pain-radar digest SideProject --top 7

# Archive format with methodology
pain-radar digest SideProject --format archive -o archive.md

# Save to file
pain-radar digest SideProject -o digest.md
```

### `pain-radar reply-template`

Generate helpful comment reply templates:

```bash
pain-radar reply-template "Stripe Connect integration issues" --count 14 --approaches "webhooks,polling,third-party middleware"
```

## Alerting & Watchlists

Create keyword watchlists to get notified when specific pain points are detected.

### `pain-radar alerts-add`

Create a new watchlist:

```bash
# Track payment-related pain points
pain-radar alerts-add "stripe, payment, checkout" --name "Payment Pain"

# Track specific subreddits only
pain-radar alerts-add "onboarding, churn" -s "SaaS,IndieHackers" --name "Retention Issues"

# With email notification (coming soon)
pain-radar alerts-add "api, integration" -e "me@email.com"
```

### `pain-radar alerts`

List all active watchlists:

```bash
pain-radar alerts
pain-radar alerts --all  # Include inactive
```

### `pain-radar alerts-check`

Check for new matches against your watchlists:

```bash
pain-radar alerts-check              # Last 24 hours
pain-radar alerts-check --hours 48   # Last 48 hours
```

### `pain-radar alerts-matches`

View all matches:

```bash
pain-radar alerts-matches
pain-radar alerts-matches 1  # Filter by watchlist ID
```

### `pain-radar alerts-remove`

Deactivate a watchlist:

```bash
pain-radar alerts-remove 1
```


## How It Works

1. **RSS Feeds**: Fetches posts from `https://reddit.com/r/{subreddit}/new.rss`
2. **JSON Comments**: Scrapes comments from public JSON endpoints
3. **AI Analysis**: Uses GPT-4o to extract pain signals with quotes
4. **Clustering**: Groups similar pain points into actionable clusters
5. **Digest Generation**: Creates Reddit-ready posts with sources

## Methodology

Pain Radar is designed to be transparent and ethical:

- **No private data**: Only public RSS/JSON endpoints
- **Filters self-promo**: AI is instructed to skip promotional posts
- **Cites sources**: Every quote links to the original thread
- **No auto-outreach**: Only DM users who opt-in via "alerts" comments
- **Open methodology**: We explain how signals are detected and clustered

## Signal Types

The AI extracts these types of evidence:

| Signal | Description |
|--------|-------------|
| `pain` | Expression of frustration or problem |
| `willingness_to_pay` | Mentions of budget, price, payment |
| `alternatives` | Existing solutions tried that failed |
| `urgency` | Time pressure, deadlines |
| `repetition` | Multiple people with same issue |
| `budget` | Specific money amounts mentioned |

## Weekly Digest Strategy

Pain Radar supports the "earn trust first, then ask" approach:

1. **Week 1-2**: Post weekly digests, comment helpfully
2. **Week 3**: Add soft CTA: "I built a simple alert tool for this"
3. **Week 4**: Ask for feedback: "What would make this worth $20/mo?"

### Post Title Templates

- "Top 7 problems people are repeatedly posting about in r/X this week (with links)"
- "I tracked 200 posts and clustered the recurring pain points. Here are the patterns."
- "This week's top pain points in r/X (with verbatim quotes)"

### Comment Reply Template

```
I track these threads and this comes up a lot. I've seen 14+ similar posts recently.

The pattern: [brief description]

What people typically try: [approach 1], [approach 2], [approach 3]

Similar threads if helpful:
- [Thread 1](link)
- [Thread 2](link)

If you want the full cluster list or alerts when this topic pops up, reply 'alerts'.
```

## Project Structure

```
src/pain_radar/
├── cli/                 # CLI subcommands
│   ├── __init__.py     # App setup + version
│   ├── pipeline.py     # run command
│   ├── fetch.py        # fetch command
│   ├── cluster.py      # cluster + digest commands
│   ├── ideas.py        # top, show, export (signals)
│   └── report.py       # report, runs
├── store/               # Storage layer
│   ├── schema.py       # SQL schema
│   └── core.py         # AsyncStore class
├── prompts.py           # LLM prompts (PainRadar personality)
├── cluster.py           # Clustering logic
├── digest.py            # Digest generation
├── reddit_async.py      # RSS + JSON scraping
├── models.py            # Pydantic models
└── config.py            # Pydantic Settings
```

## Rate Limiting

Reddit may rate-limit aggressive scraping. Built-in protections:

- **Connection pooling**: Max 20 connections, 10 keepalive
- **Semaphore concurrency**: Default 8 concurrent requests
- **Polite delays**: 0.5s between comment fetches
- **429 handling**: Respects `Retry-After` header
- **Tenacity retries**: Exponential backoff with jitter

If you see 429 errors, reduce `PAIN_RADAR_MAX_CONCURRENCY` in your `.env`.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run linting manually
ruff check src/

# Run tests with coverage
pytest --cov=src

# Run all pre-commit hooks on all files
pre-commit run --all-files
```

## License

MIT
