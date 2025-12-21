import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.language_models import BaseChatModel
from pain_radar.models import FullAnalysis, PainSignal, SignalScore, ExtractionState, Cluster, ClusterItem, EvidenceSignal, DistributionWedge, ExtractionType
from pain_radar.reddit_async import RedditPost

@pytest.fixture
def mock_llm():
    """Mock LangChain Chat Model."""
    llm = MagicMock(spec=BaseChatModel)
    llm.with_structured_output.return_value = llm  # Allow chaining
    llm.ainvoke = AsyncMock()
    return llm

@pytest.fixture
def sample_post():
    """Sample RedditPost for testing."""
    return RedditPost(
        id="test_id",
        title="Test Title",
        body="Test Body",
        url="http://test.url",
        author="test_author",
        subreddit="test_subreddit",
        created_utc=1234567890.0,
        score=10,
        num_comments=5,
        top_comments=["Comment 1", "Comment 2"]
    )

@pytest.fixture
def sample_full_analysis_extracted():
    """Sample FullAnalysis result (EXTRACTED)."""
    return FullAnalysis(
        extraction=PainSignal(
            extraction_state=ExtractionState.EXTRACTED,
            extraction_type=ExtractionType.PAIN,
            pain_point="Cannot find X",
            signal_summary="User struggles to find X",
            evidence_strength=8,
            evidence=[
                EvidenceSignal(
                    quote="I can't find X",
                    source="post",
                    signal_type="pain"
                )
            ],
            risk_flags=[]
        ),
        score=SignalScore(
            disqualified=False,
            practicality=8,
            profitability=7,
            distribution=8,
            competition=9,
            moat=5,
            confidence=0.9,
            distribution_wedge=DistributionWedge.SEO,
            distribution_wedge_detail="SEO for X",
            competition_landscape=[]
        )
    )

@pytest.fixture
def sample_cluster_item():
    return ClusterItem(
        id=1,
        summary="Summary 1",
        pain_point="Pain 1",
        subreddit="sub1",
        url="http://test.url/1",
        evidence=[
            EvidenceSignal(
                quote="Quote 1",
                signal_type="pain", 
                source="post"
            )
        ]
    )