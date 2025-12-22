"""Idea deduplication using rapidfuzz for better string similarity.

Uses token-based similarity for more accurate matching of semantically
similar ideas, even with different word order or phrasing.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from .logging_config import get_logger
from .models import PainSignal

logger = get_logger(__name__)


def similarity_ratio(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings using token-based matching.

    Uses token_set_ratio which is more robust to word order and partial matches.

    Args:
        a: First string
        b: Second string

    Returns:
        Similarity ratio between 0.0 and 1.0
    """
    # token_set_ratio handles word order differences and partial matches
    # Score is 0-100, normalize to 0-1
    return fuzz.token_set_ratio(a.lower(), b.lower()) / 100.0


def combined_similarity(ext1: PainSignal, ext2: PainSignal) -> float:
    """Calculate combined similarity across multiple fields.

    Uses weighted average of:
    - signal_summary (50%)
    - pain_point (25%)
    - target_user (25%)

    Args:
        ext1: First extraction
        ext2: Second extraction

    Returns:
        Combined similarity score between 0.0 and 1.0
    """
    summary_sim = similarity_ratio(ext1.signal_summary, ext2.signal_summary)
    pain_sim = similarity_ratio(ext1.pain_point, ext2.pain_point) if ext1.pain_point and ext2.pain_point else 0.0
    user_sim = similarity_ratio(ext1.target_user, ext2.target_user) if ext1.target_user and ext2.target_user else 0.0

    # Weighted average
    return (summary_sim * 0.5) + (pain_sim * 0.25) + (user_sim * 0.25)


def dedupe_ideas(
    ideas: list[tuple[str, PainSignal]],  # List of (post_id, extraction) tuples
    similarity_threshold: float = 0.75,
) -> list[tuple[str, PainSignal, list[str]]]:
    """Deduplicate ideas based on text similarity using rapidfuzz.

    Groups similar ideas together, keeping the first occurrence as canonical.

    Args:
        ideas: List of (post_id, extraction) tuples
        similarity_threshold: Minimum similarity to consider duplicates (0.0-1.0)

    Returns:
        List of (post_id, extraction, duplicate_post_ids) tuples
    """
    if not ideas:
        return []

    logger.info("deduping_ideas", count=len(ideas), threshold=similarity_threshold)

    # Track which ideas have been assigned to a cluster
    assigned = set()
    clusters: list[tuple[str, PainSignal, list[str]]] = []

    for i, (post_id, extraction) in enumerate(ideas):
        if post_id in assigned:
            continue

        # Skip not_extractable ideas (no meaningful content to dedupe)
        if extraction.signal_summary.lower().startswith("no viable"):
            assigned.add(post_id)
            clusters.append((post_id, extraction, []))
            continue

        # This idea starts a new cluster
        duplicates: list[str] = []

        # Check remaining ideas for similarity
        for j in range(i + 1, len(ideas)):
            other_post_id, other_extraction = ideas[j]
            if other_post_id in assigned:
                continue

            # Skip not_extractable ideas
            if other_extraction.signal_summary.lower().startswith("no viable"):
                continue

            # Use combined similarity across multiple fields
            sim = combined_similarity(extraction, other_extraction)

            if sim >= similarity_threshold:
                duplicates.append(other_post_id)
                assigned.add(other_post_id)
                logger.debug(
                    "duplicate_found",
                    canonical=post_id,
                    duplicate=other_post_id,
                    similarity=round(sim, 2),
                )

        assigned.add(post_id)
        clusters.append((post_id, extraction, duplicates))

    logger.info(
        "deduplication_complete",
        original_count=len(ideas),
        cluster_count=len(clusters),
        duplicates_removed=len(ideas) - len(clusters),
    )

    return clusters
