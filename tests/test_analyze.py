import pytest
from unittest.mock import MagicMock
from pain_radar.analyze import analyze_post, LLMAnalysisError
from pain_radar.models import FullAnalysis, ExtractionState, PainSignal, ExtractionType

@pytest.mark.asyncio
async def test_extract_pain_signals_success(mock_llm, sample_post, sample_full_analysis_extracted):
    """Test successful extraction of pain signals."""
    # Setup mock
    mock_llm.with_structured_output.return_value = mock_llm
    mock_llm.ainvoke.return_value = sample_full_analysis_extracted

    # Execute
    result = await analyze_post(mock_llm, sample_post)

    # Verify
    assert isinstance(result, FullAnalysis)
    assert result.extraction.extraction_state == ExtractionState.EXTRACTED
    assert result.extraction.pain_point == "Cannot find X"
    assert result.score.confidence == 0.9
    
    # Verify chain invocation
    mock_llm.ainvoke.assert_called_once()
    prompt_value = mock_llm.ainvoke.call_args[0][0]
    
    # Verify the prompt contains our input data
    # ChatPromptValue should convert to messages
    messages = prompt_value.to_messages()
    combined_content = " ".join([m.content for m in messages])
    
    assert sample_post.title in combined_content
    assert sample_post.body in combined_content
    assert "Comment 1" in combined_content

@pytest.mark.asyncio
async def test_extract_pain_signals_negative(mock_llm, sample_post):
    """Test extraction when no pain signals are found."""
    # Setup mock for no extraction
    empty_analysis = FullAnalysis(
        extraction=PainSignal(
            extraction_state=ExtractionState.NOT_EXTRACTABLE,
            extraction_type=ExtractionType.PAIN,
            not_extractable_reason="Just a question",
            signal_summary="No signal",
            evidence=[],
            risk_flags=[]
        ),
        score=None
    )
    mock_llm.with_structured_output.return_value = mock_llm
    mock_llm.ainvoke.return_value = empty_analysis

    # Execute
    result = await analyze_post(mock_llm, sample_post)

    # Verify
    assert result.extraction.extraction_state == ExtractionState.NOT_EXTRACTABLE
    assert result.score is None

@pytest.mark.asyncio
async def test_extract_pain_signals_disqualified(mock_llm, sample_post):
    """Test filtering of disqualified posts (e.g. self-promotion)."""
    disqualified_analysis = FullAnalysis(
        extraction=PainSignal(
            extraction_state=ExtractionState.DISQUALIFIED,
            extraction_type=ExtractionType.IDEA,
            signal_summary="User promoting their own tool",
            not_extractable_reason=None,
            evidence=[],
            risk_flags=["Self-promotion detected"]
        ),
        score=None
    )
    mock_llm.with_structured_output.return_value = mock_llm
    mock_llm.ainvoke.return_value = disqualified_analysis

    # Execute
    result = await analyze_post(mock_llm, sample_post)

    # Verify
    assert result.extraction.extraction_state == ExtractionState.DISQUALIFIED
    assert result.extraction.risk_flags == ["Self-promotion detected"]

@pytest.mark.asyncio
async def test_extract_pain_signals_error(mock_llm, sample_post):
    """Test handling of LLM errors."""
    mock_llm.with_structured_output.return_value = mock_llm
    mock_llm.ainvoke.side_effect = Exception("API Error")

    with pytest.raises(LLMAnalysisError, match="Failed to analyze post"):
        await analyze_post(mock_llm, sample_post)