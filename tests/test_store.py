import pytest
import aiosqlite
import os
import json
from pain_radar.store.core import AsyncStore
from pain_radar.models import FullAnalysis, ExtractionState, PainSignal, SignalScore, DistributionWedge, ExtractionType, CompetitorNote
from pain_radar.reddit_async import RedditPost

@pytest.mark.asyncio
async def test_async_store_connect_and_init():
    """Test that we can connect to the database and initialize the schema."""
    db_path = ":memory:" # Use in-memory for testing
    store = AsyncStore(db_path)
    
    # Verify not connected initially
    assert store._connection is None
    
    # Connect
    await store.connect()
    assert store._connection is not None
    
    # Init DB
    await store.init_db()
    
    # Verify tables exist by querying sqlite_master
    async with store.connection() as conn:
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in await cursor.fetchall()]
        assert "posts" in tables
        assert "signals" in tables
        assert "runs" in tables
        assert "clusters" in tables
        assert "watchlists" in tables
        assert "source_sets" in tables
        assert "alert_matches" in tables

    # Close connection
    await store.close()
    assert store._connection is None

@pytest.mark.asyncio
async def test_async_store_connection_context_manager():
    """Test that the connection context manager works as expected."""
    db_path = ":memory:"
    store = AsyncStore(db_path)
    
    async with store.connection() as conn:
        assert store._connection is not None
        assert isinstance(conn, aiosqlite.Connection)
        
    assert store._connection is not None
    await store.close()

@pytest.mark.asyncio
async def test_async_store_signal_crud(sample_post, sample_full_analysis_extracted):
    """Test CRUD operations for Signals."""
    db_path = ":memory:"
    store = AsyncStore(db_path)
    await store.init_db()
    
    # 1. Upsert Post (Foreign key dependency)
    await store.upsert_posts([sample_post])
    
    # 2. Save Signal
    signal_id = await store.save_signal(
        post=sample_post,
        extraction=sample_full_analysis_extracted.extraction,
        score=sample_full_analysis_extracted.score
    )
    assert signal_id > 0
    
    # 3. Get Signal Detail
    detail = await store.get_signal_detail(signal_id)
    assert detail is not None
    assert detail["post_id"] == sample_post.id
    assert detail["signal_summary"] == sample_full_analysis_extracted.extraction.signal_summary
    assert detail["total_score"] == sample_full_analysis_extracted.score.total
    
    # 4. Get Top Signals
    top = await store.get_top_signals(limit=10)
    assert len(top) == 1
    assert top[0]["id"] == signal_id
    
    # 5. Get Stats
    stats = await store.get_stats()
    assert stats["total_posts"] == 1
    assert stats["total_signals"] == 1
    assert stats["qualified_signals"] == 1
    
    await store.close()

@pytest.mark.asyncio
async def test_async_store_disqualified_signal(sample_post):
    """Test saving a disqualified signal."""
    db_path = ":memory:"
    store = AsyncStore(db_path)
    await store.init_db()
    await store.upsert_posts([sample_post])
    
    extraction = PainSignal(
        extraction_state=ExtractionState.DISQUALIFIED,
        extraction_type=ExtractionType.IDEA,
        signal_summary="Self-promotion",
        risk_flags=["self_promo"],
        evidence=[],
    )
    
    score = SignalScore(
        disqualified=True,
        disqualify_reasons=["Self-promotion"],
        practicality=0, profitability=0, distribution=0, competition=0, moat=0,
        confidence=1.0,
        distribution_wedge=DistributionWedge.COMMUNITY,
        distribution_wedge_detail="N/A",
        competition_landscape=[CompetitorNote(category="N/A", your_wedge="N/A")]
    )
    
    signal_id = await store.save_signal(post=sample_post, extraction=extraction, score=score)
    detail = await store.get_signal_detail(signal_id)
    assert detail["disqualified"] == 1
    
    await store.close()

@pytest.mark.asyncio
async def test_async_store_source_set_crud():
    """Test CRUD operations for SourceSets."""
    db_path = ":memory:"
    store = AsyncStore(db_path)
    await store.init_db()
    
    # 1. Create Source Set
    ss_id = await store.create_source_set(
        name="Test Set",
        subreddits=["sub1", "sub2"],
        description="A test set",
        preset_key="test_preset"
    )
    assert ss_id > 0
    
    # 2. Get Source Sets
    sets = await store.get_source_sets()
    assert len(sets) == 1
    assert sets[0]["name"] == "Test Set"
    assert sets[0]["subreddits"] == ["sub1", "sub2"]
    
    # 3. Get Specific Source Set
    ss = await store.get_source_set(ss_id)
    assert ss is not None
    assert ss["name"] == "Test Set"
    
    # 4. Get by Preset
    ss_preset = await store.get_source_set_by_preset("test_preset")
    assert ss_preset is not None
    assert ss_preset["id"] == ss_id
    
    # 5. Update
    await store.update_source_set(ss_id, name="Updated Name", subreddits=["sub3"])
    ss_updated = await store.get_source_set(ss_id)
    assert ss_updated["name"] == "Updated Name"
    assert ss_updated["subreddits"] == ["sub3"]
    
    # 6. Get All Active Subreddits
    all_subs = await store.get_all_active_subreddits()
    assert all_subs == ["sub3"]
    
    # 7. Delete (Deactivate)
    await store.delete_source_set(ss_id)
    sets_active = await store.get_source_sets(active_only=True)
    assert len(sets_active) == 0
    
    await store.close()
