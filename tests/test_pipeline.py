import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pain_radar.pipeline import run_pipeline, process_post, PipelineResult, LLMAnalysisError
from pain_radar.config import Settings
from pain_radar.models import FullAnalysis, ExtractionState

@pytest.fixture(autouse=True)
def mock_progress():
    """Mock progress bar utilities to avoid console output/errors in tests."""
    with patch("pain_radar.pipeline.start_fetch_task"), \
         patch("pain_radar.pipeline.complete_fetch"), \
         patch("pain_radar.pipeline.start_analyze_task"), \
         patch("pain_radar.pipeline.advance_analyze"), \
         patch("pain_radar.pipeline.complete_analyze"):
        yield

@pytest.mark.asyncio
async def test_process_post_success(mock_llm, sample_post, sample_full_analysis_extracted):
    """Test successful processing of a single post."""
    mock_store = MagicMock()
    mock_store.save_signal = AsyncMock(return_value=1)
    sem = asyncio.Semaphore(1)
    
    with patch("pain_radar.pipeline.analyze_post", return_value=sample_full_analysis_extracted):
        post_id, analysis, error = await process_post(mock_llm, mock_store, sample_post, sem)
        
        assert post_id == sample_post.id
        assert analysis == sample_full_analysis_extracted
        assert error is None
        mock_store.save_signal.assert_called_once()

@pytest.mark.asyncio
async def test_process_post_llm_error(mock_llm, sample_post):
    """Test processing when LLM analysis fails with LLMAnalysisError."""
    mock_store = MagicMock()
    sem = asyncio.Semaphore(1)
    
    with patch("pain_radar.pipeline.analyze_post", side_effect=LLMAnalysisError("API Down")):
        post_id, analysis, error = await process_post(mock_llm, mock_store, sample_post, sem)
        
        assert post_id == sample_post.id
        assert analysis is None
        assert "API Down" in error

@pytest.mark.asyncio
async def test_process_post_generic_error(mock_llm, sample_post):
    """Test processing when an unexpected error occurs."""
    mock_store = MagicMock()
    sem = asyncio.Semaphore(1)
    
    with patch("pain_radar.pipeline.analyze_post", side_effect=Exception("Unexpected")):
        post_id, analysis, error = await process_post(mock_llm, mock_store, sample_post, sem)
        
        assert post_id == sample_post.id
        assert analysis is None
        assert "Unexpected" in error

@pytest.mark.asyncio
async def test_run_pipeline_fetch_new(mock_llm, sample_post, sample_full_analysis_extracted):
    """Test running the full pipeline with new post fetching."""
    class MockRunSettings:
        def __init__(self):
            self.subreddits = ["test"]
            self.listing = "new"
            self.posts_per_subreddit = 5
            self.top_comments = 5
            self.max_concurrency = 1
            self.db_path = ":memory:"
            self.user_agent = "test-agent"

    settings = MockRunSettings()
    
    with patch("pain_radar.pipeline.fetch_all_subreddits", return_value=[sample_post]) as mock_fetch, \
         patch("pain_radar.pipeline.analyze_post", return_value=sample_full_analysis_extracted) as mock_analyze:
        
        with patch("pain_radar.pipeline.AsyncStore") as mock_store_cls:
            mock_store = mock_store_cls.return_value
            mock_store.connect = AsyncMock()
            mock_store.init_db = AsyncMock()
            mock_store.close = AsyncMock()
            mock_store.create_run = AsyncMock(return_value=1)
            mock_store.upsert_posts = AsyncMock()
            mock_store.save_signal = AsyncMock()
            mock_store.get_top_signals = AsyncMock(return_value=[])
            mock_store.get_stats = AsyncMock(return_value={})
            mock_store.update_run = AsyncMock()
            
            result = await run_pipeline(settings, mock_llm, fetch_new=True)
            
            assert isinstance(result, PipelineResult)
            assert result.posts_fetched == 1
            mock_fetch.assert_called_once()
            mock_analyze.assert_called_once()

@pytest.mark.asyncio
async def test_run_pipeline_error(mock_llm):
    """Test pipeline failure handling."""
    class MockRunSettings:
        def __init__(self):
            self.subreddits = ["test"]
            self.listing = "new"
            self.posts_per_subreddit = 5
            self.top_comments = 5
            self.max_concurrency = 1
            self.db_path = ":memory:"
            self.user_agent = "test-agent"

    settings = MockRunSettings()
    
    with patch("pain_radar.pipeline.AsyncStore") as mock_store_cls:
        mock_store = mock_store_cls.return_value
        mock_store.connect = AsyncMock()
        mock_store.init_db = AsyncMock()
        mock_store.close = AsyncMock()
        mock_store.create_run = AsyncMock(return_value=1)
        mock_store.update_run = AsyncMock()
        
        # Force an error in fetch
        with patch("pain_radar.pipeline.fetch_all_subreddits", side_effect=Exception("Fetch failed")):
            with pytest.raises(Exception, match="Fetch failed"):
                await run_pipeline(settings, mock_llm)
            
            # Verify run was updated as failed
            mock_store.update_run.assert_called_with(
                run_id=1,
                posts_fetched=0,
                posts_analyzed=0,
                signals_saved=0,
                qualified_signals=0,
                errors=1,
                status="failed"
            )

import asyncio
