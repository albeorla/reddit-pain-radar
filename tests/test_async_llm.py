import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pain_radar.extract_async import extract_idea
from pain_radar.score_async import score_idea
from pain_radar.reddit_async import RedditPost
from pain_radar.models import PainSignal, SignalScore, ExtractionState, DistributionWedge, CompetitorNote

@pytest.mark.asyncio
async def test_extract_idea():
    """Test async idea extraction with LLM mock."""
    mock_llm = MagicMock()
    mock_chain = AsyncMock()
    
    # Return a PainSignal from the chain
    expected_signal = PainSignal(
        extraction_state=ExtractionState.EXTRACTED,
        signal_summary="Test Summary",
        pain_point="Test Pain",
        target_user="Test User"
    )
    mock_chain.ainvoke.return_value = expected_signal
    
    # Mock llm.with_structured_output to return our mock chain
    mock_llm.with_structured_output.return_value = mock_chain
    
    post = RedditPost(
        id="p1", subreddit="test", title="Title", body="Body", 
        created_utc=0, score=0, num_comments=0, url="", permalink="", 
        top_comments=["comment1"]
    )
    
    # Need to patch the pipe operator or just use our mock
    # extract_idea uses: chain = EXTRACT_PROMPT | llm.with_structured_output(PainSignal)
    # This might be tricky to mock exact chain behavior, so let's patch the whole chain in the module.
    
    with patch("pain_radar.extract_async.EXTRACT_PROMPT") as mock_prompt:
        mock_prompt.__or__.return_value = mock_chain
        
        result = await extract_idea(mock_llm, post)
        assert result == expected_signal
        assert result.signal_summary == "Test Summary"

@pytest.mark.asyncio
async def test_score_idea():
    """Test async idea scoring with LLM mock."""
    mock_llm = MagicMock()
    mock_chain = AsyncMock()
    
    expected_score = SignalScore(
        disqualified=False,
        practicality=7, profitability=7, distribution=7, competition=7, moat=7,
        confidence=0.8,
        distribution_wedge=DistributionWedge.SEO,
        distribution_wedge_detail="SEO",
        competition_landscape=[CompetitorNote(category="C1", examples=[], your_wedge="W")],
        why=[], next_validation_steps=[]
    )
    mock_chain.ainvoke.return_value = expected_score
    mock_llm.with_structured_output.return_value = mock_chain
    
    extraction = PainSignal(
        extraction_state=ExtractionState.EXTRACTED,
        signal_summary="Summary"
    )
    
    with patch("pain_radar.score_async.SCORE_PROMPT") as mock_prompt:
        mock_prompt.__or__.return_value = mock_chain
        
        result = await score_idea(mock_llm, extraction)
        assert result == expected_score
        assert result.total == 35
