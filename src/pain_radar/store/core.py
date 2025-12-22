"""Core AsyncStore class for database operations."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from ..logging_config import get_logger
from ..models import Cluster, ClusterItem, EvidenceSignal
from ..reddit_async import RedditPost
from .schema import SCHEMA

logger = get_logger(__name__)


class AsyncStore:
    """Async SQLite storage for posts and signals."""

    def __init__(self, db_path: str):
        """Initialize the store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None

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

    async def upsert_posts(self, posts: list[RedditPost]) -> int:
        """Insert or update posts.

        Args:
            posts: List of RedditPost objects

        Returns:
            Number of posts upserted
        """
        async with self.connection() as conn:
            now = datetime.now(UTC).isoformat()
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

    async def get_unprocessed_posts(self, limit: int = 100) -> list[RedditPost]:
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
            await conn.execute("UPDATE posts SET processed = 1 WHERE id = ?", (post_id,))
            await conn.commit()

    async def save_signal(
        self,
        post: RedditPost,
        extraction: Any,
        score: Any | None = None,
        cluster_id: str | None = None,
        run_id: int | None = None,
    ) -> int:
        """Save an extracted and scored signal.

        Args:
            post: Source Reddit post
            extraction: PainSignal Pydantic model
            score: SignalScore Pydantic model (None if not_extractable)
            cluster_id: Optional cluster identifier
            run_id: Optional run ID to associate with this signal

        Returns:
            ID of the inserted signal
        """
        async with self.connection() as conn:
            now = datetime.now(UTC).isoformat()

            # Serialize evidence with attribution
            evidence_json = json.dumps([e.model_dump() for e in extraction.evidence]) if extraction.evidence else "[]"

            # Build legacy evidence_signals for backward compatibility
            legacy_signals = [e.quote for e in extraction.evidence] if extraction.evidence else []

            # Get extraction state
            extraction_state = (
                extraction.extraction_state.value
                if hasattr(extraction.extraction_state, "value")
                else str(extraction.extraction_state)
            )

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
                distribution_wedge = (
                    score.distribution_wedge.value
                    if hasattr(score.distribution_wedge, "value")
                    else str(score.distribution_wedge)
                )
                distribution_wedge_detail = score.distribution_wedge_detail
                competition_landscape = (
                    json.dumps([c.model_dump() for c in score.competition_landscape])
                    if score.competition_landscape
                    else "[]"
                )
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
                INSERT INTO signals (
                    post_id, run_id, cluster_id, 
                    extraction_state, not_extractable_reason,
                    signal_summary, target_user, pain_point,
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
                    extraction.signal_summary,
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

            signal_id = cursor.lastrowid
            logger.info(
                "signal_saved",
                signal_id=signal_id,
                post_id=post.id,
                extraction_state=extraction_state,
                total_score=total_score,
                evidence_strength=extraction.evidence_strength,
                disqualified=bool(disqualified),
            )
            return signal_id

    async def get_top_signals(self, limit: int = 20, include_disqualified: bool = False) -> list[dict]:
        """Get top-scored signals.

        Args:
            limit: Maximum number of signals to return
            include_disqualified: Whether to include disqualified signals

        Returns:
            List of signal dictionaries
        """
        async with self.connection() as conn:
            query = """
                SELECT i.*, p.title as post_title, p.subreddit, p.permalink
                FROM signals i
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

            cursor = await conn.execute("SELECT COUNT(*) FROM signals")
            stats["total_signals"] = (await cursor.fetchone())[0]

            cursor = await conn.execute("SELECT COUNT(*) FROM signals WHERE disqualified = 0")
            stats["qualified_signals"] = (await cursor.fetchone())[0]

            cursor = await conn.execute("SELECT AVG(total_score) FROM signals WHERE disqualified = 0")
            avg = (await cursor.fetchone())[0]
            stats["avg_score"] = round(avg, 2) if avg else 0

            return stats

    # --- Run Management ---

    async def create_run(self, subreddits: list[str]) -> int:
        """Create a new pipeline run record.

        Args:
            subreddits: List of subreddits being processed

        Returns:
            Run ID
        """
        async with self.connection() as conn:
            now = datetime.now(UTC).isoformat()
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
        signals_saved: int = 0,
        qualified_signals: int = 0,
        errors: int = 0,
        status: str = "completed",
        report_path: str | None = None,
    ) -> None:
        """Update a run record with results.

        Args:
            run_id: Run ID to update
            posts_fetched: Number of posts fetched
            posts_analyzed: Number of posts analyzed
            signals_saved: Number of signals saved
            qualified_signals: Number of qualified signals
            errors: Number of errors
            status: Run status
            report_path: Path to generated report
        """
        async with self.connection() as conn:
            now = datetime.now(UTC).isoformat()
            await conn.execute(
                """
                UPDATE runs SET
                    completed_at = ?,
                    posts_fetched = ?,
                    posts_analyzed = ?,
                    signals_saved = ?,
                    qualified_signals = ?,
                    errors = ?,
                    status = ?,
                    report_path = ?
                WHERE id = ?
                """,
                (
                    now,
                    posts_fetched,
                    posts_analyzed,
                    signals_saved,
                    qualified_signals,
                    errors,
                    status,
                    report_path,
                    run_id,
                ),
            )
            await conn.commit()

    async def get_runs(self, limit: int = 10) -> list[dict]:
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

    async def get_run(self, run_id: int) -> dict | None:
        """Get a specific run by ID.

        Args:
            run_id: Run ID

        Returns:
            Run dictionary or None
        """
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_signals_for_run(self, run_id: int) -> list[dict]:
        """Get all signals from a specific run.

        Args:
            run_id: Run ID

        Returns:
            List of signal dictionaries with post info
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT i.*, p.title as post_title, p.subreddit, p.permalink,
                       p.body as post_body, p.top_comments
                FROM signals i
                JOIN posts p ON i.post_id = p.id
                WHERE i.run_id = ?
                ORDER BY i.total_score DESC
                """,
                (run_id,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_signal_detail(self, signal_id: int) -> dict | None:
        """Get detailed information about a specific signal.

        Args:
            signal_id: Signal ID

        Returns:
            Detailed signal dictionary or None
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT i.*, p.title as post_title, p.subreddit, p.permalink,
                       p.body as post_body, p.top_comments, p.url as post_url
                FROM signals i
                JOIN posts p ON i.post_id = p.id
                WHERE i.id = ?
                """,
                (signal_id,),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_unclustered_pain_points(self, subreddit: str | None = None, days: int = 7) -> list[ClusterItem]:
        """Get extraction items available for clustering.

        Args:
            subreddit: Filter by subreddit
            days: Look back days

        Returns:
            List of ClusterItems
        """
        async with self.connection() as conn:
            query = """
                SELECT i.id, i.signal_summary, i.pain_point, i.evidence, 
                       p.subreddit, p.url
                FROM signals i
                JOIN posts p ON i.post_id = p.id
                WHERE i.cluster_id IS NULL
                AND i.disqualified = 0
                AND datetime(i.created_at) > datetime('now', ?)
            """
            params = [f"-{days} days"]

            if subreddit:
                query += " AND p.subreddit = ?"
                params.append(subreddit)

            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

        items = []
        for row in rows:
            evidence_data = json.loads(row["evidence"] or "[]")
            evidence = [EvidenceSignal(**e) for e in evidence_data]

            items.append(
                ClusterItem(
                    id=row["id"],
                    summary=row["signal_summary"],
                    pain_point=row["pain_point"],
                    subreddit=row["subreddit"],
                    url=row["url"],
                    evidence=evidence,
                )
            )

        return items

    async def save_clusters(self, clusters: list[Cluster], week_start: str) -> None:
        """Save generated clusters and link signals.

        Args:
            clusters: List of Cluster objects
            week_start: ISO date string for the week
        """
        async with self.connection() as conn:
            now = datetime.now(UTC).isoformat()

            for cluster in clusters:
                # Generate a simple ID if not present (handled by caller usually, but let's make one)
                cluster_id = f"{week_start}_{cluster.title[:10].replace(' ', '_').lower()}_{len(cluster.signal_ids)}"

                # Insert cluster
                await conn.execute(
                    """
                    INSERT INTO clusters (id, title, summary, week_start, target_audience, why_it_matters, generated_report, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cluster_id,
                        cluster.title,
                        cluster.summary,
                        week_start,
                        cluster.target_audience,
                        cluster.why_it_matters,
                        "",  # No report initially, generated later or on fly
                        now,
                    ),
                )

                # Update signals with cluster_id
                for signal_id in cluster.signal_ids:
                    await conn.execute("UPDATE signals SET cluster_id = ? WHERE id = ?", (cluster_id, signal_id))

            await conn.commit()

    # --- Watchlist / Alerting Methods ---

    async def create_watchlist(
        self,
        name: str,
        keywords: list[str],
        subreddits: list[str] | None = None,
        notification_email: str | None = None,
        notification_webhook: str | None = None,
        tier: str = "free",
    ) -> int:
        """Create a new watchlist for keyword alerts.

        Args:
            name: Name for the watchlist
            keywords: List of keywords to track
            subreddits: Optional list of subreddits to filter (None = all)
            notification_email: Email for notifications
            notification_webhook: Webhook URL for notifications
            tier: Pricing tier (free/paid)

        Returns:
            Watchlist ID
        """
        async with self.connection() as conn:
            now = datetime.now(UTC).isoformat()
            cursor = await conn.execute(
                """
                INSERT INTO watchlists 
                (name, keywords, subreddits, notification_email, notification_webhook, tier, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    name,
                    json.dumps(keywords),
                    json.dumps(subreddits) if subreddits else None,
                    notification_email,
                    notification_webhook,
                    tier,
                    now,
                ),
            )
            await conn.commit()
            watchlist_id = cursor.lastrowid
            logger.info("watchlist_created", id=watchlist_id, name=name, keywords=keywords)
            return watchlist_id

    async def get_watchlists(self, active_only: bool = True) -> list[dict]:
        """Get all watchlists.

        Args:
            active_only: Only return active watchlists

        Returns:
            List of watchlist dictionaries
        """
        async with self.connection() as conn:
            query = "SELECT * FROM watchlists"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY created_at DESC"

            cursor = await conn.execute(query)
            rows = await cursor.fetchall()

        watchlists = []
        for row in rows:
            wl = dict(row)
            wl["keywords"] = json.loads(wl["keywords"])
            wl["subreddits"] = json.loads(wl["subreddits"]) if wl["subreddits"] else None
            watchlists.append(wl)
        return watchlists

    async def get_watchlist(self, watchlist_id: int) -> dict | None:
        """Get a specific watchlist by ID.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            Watchlist dictionary or None
        """
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT * FROM watchlists WHERE id = ?", (watchlist_id,))
            row = await cursor.fetchone()

        if not row:
            return None
        wl = dict(row)
        wl["keywords"] = json.loads(wl["keywords"])
        wl["subreddits"] = json.loads(wl["subreddits"]) if wl["subreddits"] else None
        return wl

    async def delete_watchlist(self, watchlist_id: int) -> bool:
        """Delete (deactivate) a watchlist.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            True if deleted
        """
        async with self.connection() as conn:
            await conn.execute("UPDATE watchlists SET is_active = 0 WHERE id = ?", (watchlist_id,))
            await conn.commit()
            logger.info("watchlist_deleted", id=watchlist_id)
        return True

    async def check_watchlists(self, since_hours: int = 24) -> list[dict]:
        """Check all active watchlists against recent signals.

        Args:
            since_hours: Only check signals from the last N hours

        Returns:
            List of matches with watchlist and signal info
        """
        async with self.connection() as conn:
            # Get all active watchlists
            watchlists = await self.get_watchlists(active_only=True)

            if not watchlists:
                return []

            # Get recent signals
            cursor = await conn.execute(
                """
                SELECT i.id, i.signal_summary, i.pain_point, i.evidence,
                       p.subreddit, p.url, p.title as post_title
                FROM signals i
                JOIN posts p ON s.post_id = p.id
                WHERE datetime(i.created_at) > datetime('now', ?)
                AND s.disqualified = 0
                """,
                (f"-{since_hours} hours",),
            )
            signals = await cursor.fetchall()

        matches = []
        now = datetime.now(UTC).isoformat()

        for signal in signals:
            signal_text = f"{signal['signal_summary']} {signal['pain_point']} {signal['post_title']}".lower()

            for wl in watchlists:
                # Check subreddit filter
                if wl["subreddits"] and signal["subreddit"] not in wl["subreddits"]:
                    continue

                # Check keyword matches
                for keyword in wl["keywords"]:
                    if keyword.lower() in signal_text:
                        matches.append(
                            {
                                "watchlist_id": wl["id"],
                                "watchlist_name": wl["name"],
                                "signal_id": signal["id"],
                                "keyword_matched": keyword,
                                "signal_summary": signal["signal_summary"],
                                "pain_point": signal["pain_point"],
                                "subreddit": signal["subreddit"],
                                "url": signal["url"],
                            }
                        )
                        break  # One match per signal per watchlist

        # Save matches to database
        async with self.connection() as conn:
            for match in matches:
                # Check if already recorded
                cursor = await conn.execute(
                    "SELECT id FROM alert_matches WHERE watchlist_id = ? AND signal_id = ?",
                    (match["watchlist_id"], match["signal_id"]),
                )
                existing = await cursor.fetchone()

                if not existing:
                    await conn.execute(
                        """
                        INSERT INTO alert_matches (watchlist_id, signal_id, keyword_matched, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (match["watchlist_id"], match["signal_id"], match["keyword_matched"], now),
                    )

            await conn.commit()

        logger.info("watchlists_checked", total_matches=len(matches))
        return matches

    async def get_unnotified_matches(self, watchlist_id: int | None = None) -> list[dict]:
        """Get alert matches that haven't been notified yet.

        Args:
            watchlist_id: Optional filter by watchlist

        Returns:
            List of unnotified matches
        """
        async with self.connection() as conn:
            query = """
                SELECT am.*, w.name as watchlist_name, w.notification_email, w.notification_webhook,
                       i.signal_summary, i.pain_point, p.subreddit, p.url
                FROM alert_matches am
                JOIN watchlists w ON am.watchlist_id = w.id
                JOIN signals s ON am.signal_id = i.id
                JOIN posts p ON s.post_id = p.id
                WHERE am.notified = 0
            """
            params = []
            if watchlist_id:
                query += " AND am.watchlist_id = ?"
                params.append(watchlist_id)

            query += " ORDER BY am.created_at DESC"

            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def mark_matches_notified(self, match_ids: list[int]) -> None:
        """Mark alert matches as notified.

        Args:
            match_ids: List of match IDs to mark
        """
        if not match_ids:
            return

        async with self.connection() as conn:
            now = datetime.now(UTC).isoformat()
            placeholders = ",".join("?" * len(match_ids))
            await conn.execute(
                f"UPDATE alert_matches SET notified = 1, notified_at = ? WHERE id IN ({placeholders})",
                [now] + match_ids,
            )
            await conn.commit()

    # --- Source Sets Methods ---

    async def create_source_set(
        self,
        name: str,
        subreddits: list[str],
        description: str | None = None,
        preset_key: str | None = None,
        listing: str = "new",
        limit_per_sub: int = 25,
    ) -> int:
        """Create a new source set.

        Args:
            name: Display name for the source set
            subreddits: List of subreddit names
            description: Optional description
            preset_key: If created from a preset, the preset key
            listing: Reddit listing type (new, hot, top)
            limit_per_sub: Posts to fetch per subreddit

        Returns:
            Source set ID
        """
        async with self.connection() as conn:
            now = datetime.now(UTC).isoformat()
            cursor = await conn.execute(
                """
                INSERT INTO source_sets 
                (name, description, preset_key, subreddits, listing, limit_per_sub, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    name,
                    description,
                    preset_key,
                    json.dumps(subreddits),
                    listing,
                    limit_per_sub,
                    now,
                ),
            )
            await conn.commit()
            source_set_id = cursor.lastrowid
            logger.info("source_set_created", id=source_set_id, name=name, subreddits=subreddits)
            return source_set_id

    async def get_source_sets(self, active_only: bool = True) -> list[dict]:
        """Get all source sets.

        Args:
            active_only: Only return active source sets

        Returns:
            List of source set dictionaries
        """
        async with self.connection() as conn:
            query = "SELECT * FROM source_sets"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY created_at DESC"

            cursor = await conn.execute(query)
            rows = await cursor.fetchall()

        source_sets = []
        for row in rows:
            ss = dict(row)
            ss["subreddits"] = json.loads(ss["subreddits"])
            source_sets.append(ss)
        return source_sets

    async def get_source_set(self, source_set_id: int) -> dict | None:
        """Get a specific source set by ID.

        Args:
            source_set_id: Source set ID

        Returns:
            Source set dictionary or None
        """
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT * FROM source_sets WHERE id = ?", (source_set_id,))
            row = await cursor.fetchone()

        if not row:
            return None
        ss = dict(row)
        ss["subreddits"] = json.loads(ss["subreddits"])
        return ss

    async def get_source_set_by_preset(self, preset_key: str) -> dict | None:
        """Get a source set by its preset key.

        Args:
            preset_key: The preset key (e.g., 'indie_saas')

        Returns:
            Source set dictionary or None
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM source_sets WHERE preset_key = ? AND is_active = 1", (preset_key,)
            )
            row = await cursor.fetchone()

        if not row:
            return None
        ss = dict(row)
        ss["subreddits"] = json.loads(ss["subreddits"])
        return ss

    async def update_source_set(
        self,
        source_set_id: int,
        subreddits: list[str] | None = None,
        name: str | None = None,
        description: str | None = None,
        listing: str | None = None,
        limit_per_sub: int | None = None,
    ) -> bool:
        """Update a source set.

        Args:
            source_set_id: Source set ID
            subreddits: New subreddit list (if updating)
            name: New name (if updating)
            description: New description (if updating)
            listing: New listing type (if updating)
            limit_per_sub: New limit (if updating)

        Returns:
            True if updated
        """
        updates = []
        params = []

        if subreddits is not None:
            updates.append("subreddits = ?")
            params.append(json.dumps(subreddits))
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if listing is not None:
            updates.append("listing = ?")
            params.append(listing)
        if limit_per_sub is not None:
            updates.append("limit_per_sub = ?")
            params.append(limit_per_sub)

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(source_set_id)

        async with self.connection() as conn:
            await conn.execute(f"UPDATE source_sets SET {', '.join(updates)} WHERE id = ?", params)
            await conn.commit()
            logger.info("source_set_updated", id=source_set_id)
        return True

    async def delete_source_set(self, source_set_id: int) -> bool:
        """Delete (deactivate) a source set.

        Args:
            source_set_id: Source set ID

        Returns:
            True if deleted
        """
        async with self.connection() as conn:
            await conn.execute("UPDATE source_sets SET is_active = 0 WHERE id = ?", (source_set_id,))
            await conn.commit()
            logger.info("source_set_deleted", id=source_set_id)
        return True

    async def get_all_active_subreddits(self) -> list[str]:
        """Get all unique subreddits from active source sets.

        Returns:
            Deduplicated list of subreddit names
        """
        source_sets = await self.get_source_sets(active_only=True)
        all_subs = set()
        for ss in source_sets:
            all_subs.update(ss["subreddits"])
        return sorted(list(all_subs))
