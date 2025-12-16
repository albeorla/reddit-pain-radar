"""Simple text-based idea deduplication."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import List, Tuple

from .logging_config import get_logger
from .models import IdeaExtraction

logger = get_logger(__name__)


def similarity_ratio(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings.

    Args:
        a: First string
        b: Second string

    Returns:
        Similarity ratio between 0.0 and 1.0
    """
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def dedupe_ideas(
    ideas: List[Tuple[str, IdeaExtraction]],  # List of (post_id, extraction) tuples
    similarity_threshold: float = 0.7,
) -> List[Tuple[str, IdeaExtraction, List[str]]]:
    """Deduplicate ideas based on text similarity.

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
    clusters: List[Tuple[str, IdeaExtraction, List[str]]] = []

    for i, (post_id, extraction) in enumerate(ideas):
        if post_id in assigned:
            continue

        # This idea starts a new cluster
        duplicates: List[str] = []

        # Check remaining ideas for similarity
        for j in range(i + 1, len(ideas)):
            other_post_id, other_extraction = ideas[j]
            if other_post_id in assigned:
                continue

            # Compare idea summaries
            sim = similarity_ratio(
                extraction.idea_summary, other_extraction.idea_summary
            )

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
