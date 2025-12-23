import pytest
import asyncio
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock, AsyncMock
from pain_radar.cli import app
from pain_radar.store import AsyncStore
from pain_radar.reddit_async import RedditPost

runner = CliRunner()

@pytest.fixture
def mock_reddit_fetch():
    with patch("pain_radar.pipeline.fetch_all_subreddits", new_callable=AsyncMock) as mock:
        yield mock

@pytest.fixture
def mock_llm_chain():
    with patch("pain_radar.pipeline.ChatOpenAI") as mock:
        yield mock

def test_fetch_integration(mock_reddit_fetch, tmp_path):
    """Integration test for fetch command using real DB."""
    db_file = tmp_path / "test.db"
    
    # Setup mock reddit data
    post = RedditPost(
        id="t3_12345",
        subreddit="test",
        title="Test Post",
        body="Test Body",
        created_utc=1600000000,
        score=10,
        num_comments=5,
        url="http://url",
        permalink="/r/test/12345",
        top_comments=[]
    )
    mock_reddit_fetch.return_value = [post]
    
    # Mock settings to use our temporary DB
    with patch("pain_radar.cli.fetch.get_settings") as mock_settings:
        settings = MagicMock()
        settings.db_path = str(db_file)
        settings.listing = "new"
        settings.posts_per_subreddit = 10
        settings.top_comments = 5
        settings.max_concurrency = 1
        settings.user_agent = "test-agent"
        mock_settings.return_value = settings
        
        # Run fetch command (synchronous invocation, which calls asyncio.run inside)
        result = runner.invoke(app, ["fetch", "-s", "test"])
        
        assert result.exit_code == 0
        assert "Fetched 1 posts" in result.stdout
        
        # Verify data is in DB
        async def check_db():
            store = AsyncStore(str(db_file))
            await store.connect()
            # No init_db needed as fetch calls it? Yes, run_fetch_only calls init_db.
            
            posts = await store.get_unprocessed_posts()
            await store.close()
            return posts

        posts = asyncio.run(check_db())
        
        # Correct assertion
        assert len(posts) == 1
        assert posts[0].id == "t3_12345"

def test_run_integration(mock_reddit_fetch, tmp_path):
    """Integration test for run command (fetch + analyze) using real DB."""
    db_file = tmp_path / "test.db"
    
    # Setup mock reddit data
    post = RedditPost(
        id="t3_12345",
        subreddit="test",
        title="Test Post",
        body="I need a tool that does X.",
        created_utc=1600000000,
        score=10,
        num_comments=5,
        url="http://url",
        permalink="/r/test/12345",
        top_comments=[]
    )
    mock_reddit_fetch.return_value = [post]
    
    # Mock settings
    with patch("pain_radar.cli.pipeline.get_settings") as mock_settings:
        settings = MagicMock()
        settings.db_path = str(db_file)
        settings.listing = "new"
        settings.posts_per_subreddit = 10
        settings.top_comments = 5
        settings.max_concurrency = 1
        settings.user_agent = "test-agent"
        settings.openai_api_key = "sk-test"
        settings.openai_model = "gpt-4-test"
        mock_settings.return_value = settings
        
        # Mock analyze_post to return a valid analysis
        from pain_radar.models import FullAnalysis, PainSignal, ExtractionState, SignalScore, ExtractionType, DistributionWedge, CompetitorNote
        
        analysis = FullAnalysis(
            extraction=PainSignal(
                extraction_state=ExtractionState.EXTRACTED,
                extraction_type=ExtractionType.PAIN,
                signal_summary="Needs tool for X",
                evidence_strength=8,
                evidence=[],
            ),
            score=SignalScore(
                disqualified=False,
                practicality=8,
                profitability=8,
                distribution=8,
                competition=5,
                moat=5,
                confidence=0.9,
                distribution_wedge=DistributionWedge.SEO,
                distribution_wedge_detail="SEO",
                competition_landscape=[
                    CompetitorNote(category="Existing", examples=[], your_wedge="Better")
                ],
                why=[],
                next_validation_steps=[]
            )
        )
        
        with patch("pain_radar.pipeline.analyze_post", return_value=analysis) as mock_analyze:
            # We also need to mock ChatOpenAI construction because the CLI instantiates it
            with patch("pain_radar.cli.pipeline.ChatOpenAI"):
                # Run 'run' command
                result = runner.invoke(app, ["run", "-s", "test"])
                
                assert result.exit_code == 0
                assert "Pipeline complete" in result.stdout
                assert "Posts analyzed: 1" in result.stdout
                assert "Signals saved: 1" in result.stdout
                
                # Verify data in DB
                async def check_db():
                    store = AsyncStore(str(db_file))
                    await store.connect()
                    
                    # Check run record
                    runs = await store.get_runs()
                    assert len(runs) == 1
                    assert runs[0]["posts_analyzed"] == 1
                    
                    # Check top signals
                    signals = await store.get_top_signals()
                    await store.close()
                    return signals

                signals = asyncio.run(check_db())
                assert len(signals) == 1
                assert signals[0]["signal_summary"] == "Needs tool for X"