"""Async SQLite storage layer using aiosqlite."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, List, Optional

import aiosqlite

from .logging_config import get_logger
from .reddit_async import RedditPost

logger = get_logger(__name__)

# SQL schema for the database
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

CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL,
    run_id INTEGER,
    cluster_id TEXT,
    
    -- Extraction state
    extraction_state TEXT NOT NULL DEFAULT 'extracted',  -- extracted, not_extractable, disqualified
    not_extractable_reason TEXT,
    
    -- Extraction fields
    idea_summary TEXT NOT NULL,
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
    ideas_saved INTEGER DEFAULT 0,
    qualified_ideas INTEGER DEFAULT 0,
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
CREATE INDEX IF NOT EXISTS idx_ideas_post_id ON ideas(post_id);
CREATE INDEX IF NOT EXISTS idx_ideas_run_id ON ideas(run_id);
CREATE INDEX IF NOT EXISTS idx_ideas_total_score ON ideas(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_ideas_disqualified ON ideas(disqualified);
CREATE INDEX IF NOT EXISTS idx_ideas_extraction_state ON ideas(extraction_state);
"""


class AsyncStore:
    """Async SQLite storage for posts and ideas."""

    def __init__(self, db_path: str):
        """Initialize the store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Open database connection."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        logger.info("database_connected", path=self.db_path)

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("database_closed")

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """Context manager for database connection."""
        if not self._connection:
            await self.connect()
        yield self._connection

    async def init_db(self) -> None:
        """Initialize database schema."""
        async with self.connection() as conn:
            await conn.executescript(SCHEMA)
            await conn.commit()
        logger.info("database_initialized")

    async def upsert_posts(self, posts: List[RedditPost]) -> int:
        """Insert or update posts.

        Args:
            posts: List of RedditPost objects

        Returns:
            Number of posts upserted
        """
        async with self.connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            count = 0
            for post in posts:
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO posts 
                    (id, subreddit, title, body, created_utc, score, 
                     num_comments, url, permalink, top_comments, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        post.id,
                        post.subreddit,
                        post.title,
                        post.body,
                        post.created_utc,
                        post.score,
                        post.num_comments,
                        post.url,
                        post.permalink,
                        json.dumps(post.top_comments),
                        now,
                    ),
                )
                count += 1
            await conn.commit()
        logger.info("posts_upserted", count=count)
        return count

    async def get_unprocessed_posts(self, limit: int = 100) -> List[RedditPost]:
        """Get posts that haven't been processed yet.

        Args:
            limit: Maximum number of posts to return

        Returns:
            List of unprocessed RedditPost objects
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM posts 
                WHERE processed = 0 
                ORDER BY score DESC 
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()

        posts = []
        for row in rows:
            posts.append(
                RedditPost(
                    id=row["id"],
                    subreddit=row["subreddit"],
                    title=row["title"],
                    body=row["body"] or "",
                    created_utc=row["created_utc"],
                    score=row["score"],
                    num_comments=row["num_comments"],
                    url=row["url"] or "",
                    permalink=row["permalink"] or "",
                    top_comments=json.loads(row["top_comments"] or "[]"),
                )
            )
        return posts

    async def mark_post_processed(self, post_id: str) -> None:
        """Mark a post as processed.

        Args:
            post_id: Reddit post ID
        """
        async with self.connection() as conn:
            await conn.execute(
                "UPDATE posts SET processed = 1 WHERE id = ?", (post_id,)
            )
            await conn.commit()

    async def save_idea(
        self,
        post: RedditPost,
        extraction: Any,
        score: Optional[Any] = None,
        cluster_id: Optional[str] = None,
        run_id: Optional[int] = None,
    ) -> int:
        """Save an extracted and scored idea.

        Args:
            post: Source Reddit post
            extraction: IdeaExtraction Pydantic model
            score: IdeaScore Pydantic model (None if not_extractable)
            cluster_id: Optional cluster identifier
            run_id: Optional run ID to associate with this idea

        Returns:
            ID of the inserted idea
        """
        async with self.connection() as conn:
            now = datetime.now(timezone.utc).isoformat()

            # Serialize evidence with attribution
            evidence_json = json.dumps([e.model_dump() for e in extraction.evidence]) if extraction.evidence else "[]"
            
            # Build legacy evidence_signals for backward compatibility
            legacy_signals = [e.quote for e in extraction.evidence] if extraction.evidence else []
            
            # Get extraction state
            extraction_state = extraction.extraction_state.value if hasattr(extraction.extraction_state, 'value') else str(extraction.extraction_state)
            
            # Handle score fields (may be None for not_extractable)
            if score:
                disqualified = 1 if score.disqualified else 0
                disqualify_reasons = json.dumps(score.disqualify_reasons)
                practicality = score.practicality
                profitability = score.profitability
                distribution = score.distribution
                competition = score.competition
                moat = score.moat
                total_score = score.total
                confidence = score.confidence
                distribution_wedge = score.distribution_wedge.value if hasattr(score.distribution_wedge, 'value') else str(score.distribution_wedge)
                distribution_wedge_detail = score.distribution_wedge_detail
                competition_landscape = json.dumps([c.model_dump() for c in score.competition_landscape]) if score.competition_landscape else "[]"
                why = json.dumps(score.why)
                next_validation_steps = json.dumps(score.next_validation_steps)
                raw_score = score.model_dump_json()
            else:
                disqualified = 0
                disqualify_reasons = "[]"
                practicality = profitability = distribution = competition = moat = 0
                total_score = 0
                confidence = 0.0
                distribution_wedge = None
                distribution_wedge_detail = None
                competition_landscape = "[]"
                why = "[]"
                next_validation_steps = "[]"
                raw_score = "{}"

            cursor = await conn.execute(
                """
                INSERT INTO ideas (
                    post_id, run_id, cluster_id, 
                    extraction_state, not_extractable_reason,
                    idea_summary, target_user, pain_point,
                    proposed_solution, evidence, evidence_strength, evidence_strength_reason,
                    evidence_signals, risk_flags,
                    disqualified, disqualify_reasons, practicality, profitability,
                    distribution, competition, moat, total_score, confidence,
                    distribution_wedge, distribution_wedge_detail, competition_landscape,
                    why, next_validation_steps, created_at, raw_extraction, raw_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post.id,
                    run_id,
                    cluster_id,
                    extraction_state,
                    extraction.not_extractable_reason,
                    extraction.idea_summary,
                    extraction.target_user,
                    extraction.pain_point,
                    extraction.proposed_solution,
                    evidence_json,
                    extraction.evidence_strength,
                    extraction.evidence_strength_reason,
                    json.dumps(legacy_signals),
                    json.dumps(extraction.risk_flags),
                    disqualified,
                    disqualify_reasons,
                    practicality,
                    profitability,
                    distribution,
                    competition,
                    moat,
                    total_score,
                    confidence,
                    distribution_wedge,
                    distribution_wedge_detail,
                    competition_landscape,
                    why,
                    next_validation_steps,
                    now,
                    extraction.model_dump_json(),
                    raw_score,
                ),
            )
            await conn.commit()

            # Mark the post as processed
            await self.mark_post_processed(post.id)

            idea_id = cursor.lastrowid
            logger.info(
                "idea_saved",
                idea_id=idea_id,
                post_id=post.id,
                extraction_state=extraction_state,
                total_score=total_score,
                evidence_strength=extraction.evidence_strength,
                disqualified=bool(disqualified),
            )
            return idea_id

    async def get_top_ideas(
        self, limit: int = 20, include_disqualified: bool = False
    ) -> List[dict]:
        """Get top-scored ideas.

        Args:
            limit: Maximum number of ideas to return
            include_disqualified: Whether to include disqualified ideas

        Returns:
            List of idea dictionaries
        """
        async with self.connection() as conn:
            query = """
                SELECT i.*, p.title as post_title, p.subreddit, p.permalink
                FROM ideas i
                JOIN posts p ON i.post_id = p.id
            """
            if not include_disqualified:
                query += " WHERE i.disqualified = 0"
            query += " ORDER BY i.total_score DESC LIMIT ?"

            cursor = await conn.execute(query, (limit,))
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def get_stats(self) -> dict:
        """Get database statistics.

        Returns:
            Dictionary of statistics
        """
        async with self.connection() as conn:
            stats = {}

            cursor = await conn.execute("SELECT COUNT(*) FROM posts")
            stats["total_posts"] = (await cursor.fetchone())[0]

            cursor = await conn.execute("SELECT COUNT(*) FROM posts WHERE processed = 1")
            stats["processed_posts"] = (await cursor.fetchone())[0]

            cursor = await conn.execute("SELECT COUNT(*) FROM ideas")
            stats["total_ideas"] = (await cursor.fetchone())[0]

            cursor = await conn.execute("SELECT COUNT(*) FROM ideas WHERE disqualified = 0")
            stats["qualified_ideas"] = (await cursor.fetchone())[0]

            cursor = await conn.execute(
                "SELECT AVG(total_score) FROM ideas WHERE disqualified = 0"
            )
            avg = (await cursor.fetchone())[0]
            stats["avg_score"] = round(avg, 2) if avg else 0

            return stats

    # --- Run Management ---

    async def create_run(self, subreddits: List[str]) -> int:
        """Create a new pipeline run record.

        Args:
            subreddits: List of subreddits being processed

        Returns:
            Run ID
        """
        async with self.connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            cursor = await conn.execute(
                """
                INSERT INTO runs (started_at, subreddits, status)
                VALUES (?, ?, 'running')
                """,
                (now, json.dumps(subreddits)),
            )
            await conn.commit()
            return cursor.lastrowid

    async def update_run(
        self,
        run_id: int,
        posts_fetched: int = 0,
        posts_analyzed: int = 0,
        ideas_saved: int = 0,
        qualified_ideas: int = 0,
        errors: int = 0,
        status: str = "completed",
        report_path: Optional[str] = None,
    ) -> None:
        """Update a run record with results.

        Args:
            run_id: Run ID to update
            posts_fetched: Number of posts fetched
            posts_analyzed: Number of posts analyzed
            ideas_saved: Number of ideas saved
            qualified_ideas: Number of qualified ideas
            errors: Number of errors
            status: Run status
            report_path: Path to generated report
        """
        async with self.connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                """
                UPDATE runs SET
                    completed_at = ?,
                    posts_fetched = ?,
                    posts_analyzed = ?,
                    ideas_saved = ?,
                    qualified_ideas = ?,
                    errors = ?,
                    status = ?,
                    report_path = ?
                WHERE id = ?
                """,
                (
                    now,
                    posts_fetched,
                    posts_analyzed,
                    ideas_saved,
                    qualified_ideas,
                    errors,
                    status,
                    report_path,
                    run_id,
                ),
            )
            await conn.commit()

    async def get_runs(self, limit: int = 10) -> List[dict]:
        """Get recent pipeline runs.

        Args:
            limit: Maximum runs to return

        Returns:
            List of run dictionaries
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_run(self, run_id: int) -> Optional[dict]:
        """Get a specific run by ID.

        Args:
            run_id: Run ID

        Returns:
            Run dictionary or None
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM runs WHERE id = ?", (run_id,)
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_ideas_for_run(self, run_id: int) -> List[dict]:
        """Get all ideas from a specific run.

        Args:
            run_id: Run ID

        Returns:
            List of idea dictionaries with post info
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT i.*, p.title as post_title, p.subreddit, p.permalink,
                       p.body as post_body, p.top_comments
                FROM ideas i
                JOIN posts p ON i.post_id = p.id
                WHERE i.run_id = ?
                ORDER BY i.total_score DESC
                """,
                (run_id,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_idea_detail(self, idea_id: int) -> Optional[dict]:
        """Get detailed information about a specific idea.

        Args:
            idea_id: Idea ID

        Returns:
            Detailed idea dictionary or None
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT i.*, p.title as post_title, p.subreddit, p.permalink,
                       p.body as post_body, p.top_comments, p.url as post_url
                FROM ideas i
                JOIN posts p ON i.post_id = p.id
                WHERE i.id = ?
                """,
                (idea_id,),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

