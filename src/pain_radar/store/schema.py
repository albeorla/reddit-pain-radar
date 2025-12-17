"""Database schema for Pain Radar."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    subreddit TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    created_utc INTEGER NOT NULL,
    score INTEGER NOT NULL,
    num_comments INTEGER NOT NULL,
    url TEXT,
    permalink TEXT,
    top_comments TEXT,  -- JSON array
    fetched_at TEXT NOT NULL,
    processed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL,
    run_id INTEGER,
    cluster_id TEXT,
    
    -- Extraction state
    extraction_state TEXT NOT NULL DEFAULT 'extracted',  -- extracted, not_extractable, disqualified
    not_extractable_reason TEXT,
    
    -- Extraction fields (renamed from idea_summary for clarity)
    signal_summary TEXT NOT NULL,
    target_user TEXT,
    pain_point TEXT,
    proposed_solution TEXT,
    evidence TEXT,  -- JSON array of EvidenceSignal objects with source attribution
    evidence_strength INTEGER DEFAULT 0,
    evidence_strength_reason TEXT,
    risk_flags TEXT,  -- JSON array
    
    -- Legacy field for backward compatibility
    evidence_signals TEXT,  -- JSON array (deprecated, use evidence)
    
    -- Score fields
    disqualified INTEGER DEFAULT 0,
    disqualify_reasons TEXT,  -- JSON array
    practicality INTEGER,
    profitability INTEGER,
    distribution INTEGER,
    competition INTEGER,
    moat INTEGER,
    total_score INTEGER,
    confidence REAL,
    
    -- Enhanced distribution analysis
    distribution_wedge TEXT,  -- ecosystem, partner_channel, seo, influencer_affiliate, community, product_led
    distribution_wedge_detail TEXT,
    
    -- Enhanced competition analysis
    competition_landscape TEXT,  -- JSON array of CompetitorNote objects
    
    -- Reasoning
    why TEXT,  -- JSON array
    next_validation_steps TEXT,  -- JSON array
    
    -- Metadata
    created_at TEXT NOT NULL,
    raw_extraction TEXT,  -- Full JSON
    raw_score TEXT,  -- Full JSON
    
    FOREIGN KEY (post_id) REFERENCES posts(id),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    subreddits TEXT,  -- JSON array
    posts_fetched INTEGER DEFAULT 0,
    posts_analyzed INTEGER DEFAULT 0,
    signals_saved INTEGER DEFAULT 0,
    qualified_signals INTEGER DEFAULT 0,
    not_extractable INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running',  -- running, completed, failed
    report_path TEXT
);

CREATE TABLE IF NOT EXISTS processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL,
    status TEXT NOT NULL,  -- pending, processing, completed, failed
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

CREATE INDEX IF NOT EXISTS idx_posts_subreddit ON posts(subreddit);
CREATE INDEX IF NOT EXISTS idx_posts_processed ON posts(processed);
CREATE INDEX IF NOT EXISTS idx_signals_post_id ON signals(post_id);
CREATE INDEX IF NOT EXISTS idx_signals_run_id ON signals(run_id);
CREATE INDEX IF NOT EXISTS idx_signals_total_score ON signals(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_signals_disqualified ON signals(disqualified);
CREATE INDEX IF NOT EXISTS idx_signals_extraction_state ON signals(extraction_state);

-- Prevent duplicate signals for the same post in the same run
CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_post_run_unique ON signals(post_id, run_id);

CREATE TABLE IF NOT EXISTS clusters (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    week_start TEXT NOT NULL,  -- ISO date YYYY-MM-DD for the week
    target_audience TEXT,
    why_it_matters TEXT,
    created_at TEXT NOT NULL,
    generated_report TEXT  -- Full Markdown output
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    keyword TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    last_sent_at TEXT
);

-- Enhanced watchlists for Pain Radar alerting
CREATE TABLE IF NOT EXISTS watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    keywords TEXT NOT NULL,  -- JSON array of keywords to match
    subreddits TEXT,  -- JSON array (null = all tracked subreddits)
    notification_email TEXT,
    notification_webhook TEXT,
    tier TEXT DEFAULT 'free',  -- free, paid
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    last_checked_at TEXT,
    total_matches INTEGER DEFAULT 0
);

-- Track which signals matched which watchlists
CREATE TABLE IF NOT EXISTS alert_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL,
    signal_id INTEGER NOT NULL,
    keyword_matched TEXT NOT NULL,
    created_at TEXT NOT NULL,
    notified INTEGER DEFAULT 0,
    notified_at TEXT,
    FOREIGN KEY (watchlist_id) REFERENCES watchlists(id),
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);

-- Source sets: curated subreddit bundles for different ICPs
CREATE TABLE IF NOT EXISTS source_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    preset_key TEXT,           -- null if custom, e.g. 'indie_saas'
    subreddits TEXT NOT NULL,  -- JSON array of subreddit names
    listing TEXT DEFAULT 'new', -- new, hot, top
    limit_per_sub INTEGER DEFAULT 25,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_clusters_week ON clusters(week_start);
CREATE INDEX IF NOT EXISTS idx_alerts_email ON alerts(email);
CREATE INDEX IF NOT EXISTS idx_watchlists_active ON watchlists(is_active);
CREATE INDEX IF NOT EXISTS idx_alert_matches_watchlist ON alert_matches(watchlist_id);
CREATE INDEX IF NOT EXISTS idx_alert_matches_notified ON alert_matches(notified);
CREATE INDEX IF NOT EXISTS idx_source_sets_active ON source_sets(is_active);
CREATE INDEX IF NOT EXISTS idx_source_sets_preset ON source_sets(preset_key);
"""

# Migration from old schema (ideas -> signals)
MIGRATION_V2 = """
-- Rename ideas table to signals if it exists
ALTER TABLE ideas RENAME TO signals;

-- Rename columns
ALTER TABLE signals RENAME COLUMN idea_summary TO signal_summary;

-- Update runs table columns
ALTER TABLE runs RENAME COLUMN ideas_saved TO signals_saved;
ALTER TABLE runs RENAME COLUMN qualified_ideas TO qualified_signals;

-- Update alert_matches
ALTER TABLE alert_matches RENAME COLUMN idea_id TO signal_id;

-- Update index names (SQLite doesn't support renaming indexes, they'll be recreated)
"""
