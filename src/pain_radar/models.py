"""Pydantic models for LLM structured outputs."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class SignalType(str, Enum):
    """Type of demand signal from evidence."""

    PAIN = "pain"  # Expression of frustration or problem
    WILLINGNESS_TO_PAY = "willingness_to_pay"  # Mentions of budget, price, or payment
    ALTERNATIVES = "alternatives"  # Mentions of existing solutions tried
    URGENCY = "urgency"  # Time pressure, deadlines, "need this now"
    REPETITION = "repetition"  # Multiple people with same issue
    BUDGET = "budget"  # Specific budget mentions


class EvidenceSignal(BaseModel):
    """A single piece of evidence with source attribution."""

    quote: str = Field(..., max_length=150, description="Exact quote (max 25 words) from the source")
    source: Literal["post", "comment"] = Field(..., description="Whether this came from the post body or a comment")
    comment_index: int | None = Field(default=None, description="0-based index of the comment if source='comment'")
    signal_type: SignalType = Field(..., description="Type of demand signal this represents")


class DistributionWedge(str, Enum):
    """Primary distribution channel type."""

    ECOSYSTEM = "ecosystem"  # Stripe, Shopify, WordPress, Chrome, GitHub Marketplace
    PARTNER_CHANNEL = "partner_channel"  # Integration partners, resellers
    SEO = "seo"  # Organic search with specific query wedge
    INFLUENCER_AFFILIATE = "influencer_affiliate"  # Creator/affiliate channel
    COMMUNITY = "community"  # Existing community presence (Reddit, Discord, etc.)
    PRODUCT_LED = "product_led"  # Viral/PLG mechanics built into product


class ExtractionState(str, Enum):
    """State of idea extraction."""

    EXTRACTED = "extracted"  # Valid idea extracted and ready for scoring
    NOT_EXTRACTABLE = "not_extractable"  # No viable idea in content (meta post, question only, etc.)
    DISQUALIFIED = "disqualified"  # Idea extracted but fails rubric (scam, labor, etc.)


class ExtractionType(str, Enum):
    """Type of extraction (Solution Idea vs. Pure Pain)."""

    IDEA = "idea"  # A productizable solution concept
    PAIN = "pain"  # A raw pain point with no clear solution yet


class CompetitorNote(BaseModel):
    """A single competitor/alternative in the landscape."""

    category: str = Field(..., description="Category or type of competitor (e.g., 'CRO agencies', 'checkout plugins')")
    examples: list[str] = Field(default_factory=list, description="Known examples if any (can be empty if unknown)")
    your_wedge: str = Field(..., description="How this idea differentiates from this category")


class PainSignal(BaseModel):
    """Structured output for pain signal extraction from Reddit content."""

    extraction_state: ExtractionState = Field(..., description="Whether a viable idea was extracted")

    extraction_type: ExtractionType = Field(
        default=ExtractionType.IDEA,
        description="Type of extraction: 'idea' (has solution) or 'pain' (problem only)",
    )

    signal_summary: str = Field(
        ...,
        description="One sentence summary of the pain signal (or 'No viable signal' if not extractable)",
    )
    target_user: str = Field(default="", description="Who is the target user/customer")
    pain_point: str = Field(default="", description="What pain point does this address")
    proposed_solution: str = Field(default="", description="What is the proposed solution")

    # Enhanced evidence with attribution
    evidence: list[EvidenceSignal] = Field(default_factory=list, description="Evidence signals with source attribution")

    # Evidence strength score
    evidence_strength: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Quality of demand signals: 0-3 weak, 4-6 moderate, 7-10 strong",
    )
    evidence_strength_reason: str = Field(default="", description="Brief explanation of evidence strength score")

    risk_flags: list[str] = Field(
        default_factory=list,
        description="Potential risks or red flags identified",
    )

    not_extractable_reason: str | None = Field(
        default=None,
        description="If not extractable, why (meta post, question only, promotion, etc.)",
    )


class SignalScore(BaseModel):
    """Structured output for signal scoring and evaluation."""

    # Disqualification
    disqualified: bool = Field(..., description="Whether the signal is disqualified")
    disqualify_reasons: list[str] = Field(
        default_factory=list,
        description="Reasons for disqualification if applicable",
    )

    # Core scores
    practicality: int = Field(..., ge=0, le=10, description="Build scope, dependencies, time-to-MVP (0-10)")
    profitability: int = Field(..., ge=0, le=10, description="Pricing power, margins, buyer value (0-10)")
    distribution: int = Field(..., ge=0, le=10, description="Ability to reach buyers, channel leverage (0-10)")
    competition: int = Field(
        ...,
        ge=0,
        le=10,
        description="Saturation; higher if less crowded or has wedge (0-10)",
    )
    moat: int = Field(
        ...,
        ge=0,
        le=10,
        description="Data, workflow lock-in, niche depth, switching costs (0-10)",
    )

    @computed_field
    @property
    def total(self) -> int:
        """Sum of all dimension scores."""
        return self.practicality + self.profitability + self.distribution + self.competition + self.moat

    # Confidence
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in scoring (0.0-1.0). Lower if evidence is thin.",
    )

    # Enhanced distribution analysis
    distribution_wedge: DistributionWedge = Field(..., description="Primary distribution channel type")
    distribution_wedge_detail: str = Field(
        ...,
        description="Specific distribution strategy (e.g., 'Stripe Marketplace', 'SEO: checkout abandonment SaaS')",
    )

    # Enhanced competition analysis
    competition_landscape: list[CompetitorNote] = Field(
        default_factory=list,
        min_length=1,
        max_length=5,
        description="2-5 competitor categories with differentiation notes",
    )

    # Reasoning
    why: list[str] = Field(default_factory=list, description="One reason per dimension explaining the score")
    next_validation_steps: list[str] = Field(
        default_factory=list, description="Recommended next steps to validate the signal"
    )


class FullAnalysis(BaseModel):
    """Complete analysis output including extraction and scoring."""

    extraction: PainSignal
    score: SignalScore | None = Field(default=None, description="Score is None if extraction_state != 'extracted'")


class ClusterItem(BaseModel):
    """A minimal reference to an extracted pain signal for clustering."""

    id: int
    summary: str
    pain_point: str
    subreddit: str
    url: str
    evidence: list[EvidenceSignal]


class Cluster(BaseModel):
    """A grouped set of pain points (Pain Cluster)."""

    title: str = Field(..., description="Catchy title for the pain cluster")
    summary: str = Field(..., description="1-sentence summary of the pattern")
    target_audience: str = Field(..., description="Who is affected")
    why_it_matters: str = Field(..., description="Why this is a good opportunity")

    # IDs of signals in this cluster
    signal_ids: list[int] = Field(..., description="List of signal IDs included in this cluster")

    # Selected quotes for the digest
    quotes: list[str] = Field(..., description="2-3 best verbatim quotes illustrating the pain")

    # URLs for the digest
    urls: list[str] = Field(..., description="URLs to the source threads")


# Backward compatibility aliases (deprecated, use new names)
IdeaExtraction = PainSignal
IdeaScore = SignalScore
