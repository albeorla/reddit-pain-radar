import pytest
import os
import json
from unittest.mock import AsyncMock, MagicMock
from pain_radar.report import generate_report, generate_json_report

@pytest.mark.asyncio
async def test_generate_report(tmp_path):
    """Test generating a markdown report."""
    mock_store = MagicMock()
    mock_store.get_run = AsyncMock(return_value={
        "id": 1,
        "started_at": "2023-01-01T00:00:00",
        "subreddits": '["test"]',
        "posts_fetched": 10,
        "posts_analyzed": 5
    })
    mock_store.get_signals_for_run = AsyncMock(return_value=[
        {"id": 1, "signal_summary": "Test signal", "total_score": 40, "disqualified": False}
    ])
    mock_store.get_stats = AsyncMock(return_value={"avg_score": 40})
    
    output_dir = tmp_path / "reports"
    report_path = await generate_report(mock_store, run_id=1, output_dir=str(output_dir))
    
    assert os.path.exists(report_path)
    with open(report_path, "r") as f:
        content = f.read()
        assert "# Pain Radar Report - Run #1" in content
        assert "Test signal" in content

@pytest.mark.asyncio
async def test_generate_report_no_run_id(tmp_path):
    """Test generating a markdown report without providing run_id."""
    mock_store = MagicMock()
    mock_store.get_runs = AsyncMock(return_value=[{
        "id": 1,
        "started_at": "2023-01-01T00:00:00",
        "subreddits": '["test"]',
        "posts_fetched": 10,
        "posts_analyzed": 5
    }])
    mock_store.get_signals_for_run = AsyncMock(return_value=[
        {"id": 1, "signal_summary": "Test signal", "total_score": 40, "disqualified": False}
    ])
    mock_store.get_stats = AsyncMock(return_value={"avg_score": 40})
    
    output_dir = tmp_path / "reports"
    report_path = await generate_report(mock_store, run_id=None, output_dir=str(output_dir))
    
    assert os.path.exists(report_path)
    with open(report_path, "r") as f:
        content = f.read()
        assert "# Pain Radar Report - Run #1" in content

@pytest.mark.asyncio
async def test_generate_report_with_disqualified(tmp_path):
    """Test generating a report with disqualified signals."""
    mock_store = MagicMock()
    mock_store.get_run = AsyncMock(return_value={
        "id": 1,
        "started_at": "2023-01-01T00:00:00",
        "subreddits": '["test"]',
        "posts_fetched": 10,
        "posts_analyzed": 5
    })
    mock_store.get_signals_for_run = AsyncMock(return_value=[
        {
            "id": 1, 
            "signal_summary": "Good signal", 
            "total_score": 40, 
            "disqualified": False,
            "evidence_signals": '["ev1", "ev2"]',
            "next_validation_steps": '["step1"]',
            "why": '["why1"]',
            "permalink": "http://example.com"
        },
        {
            "id": 2, 
            "signal_summary": "Bad signal", 
            "total_score": 10, 
            "disqualified": True,
            "disqualify_reasons": '["scam", "spam"]'
        }
    ])
    mock_store.get_stats = AsyncMock(return_value={"avg_score": 25})
    
    output_dir = tmp_path / "reports"
    report_path = await generate_report(mock_store, run_id=1, output_dir=str(output_dir))
    
    assert os.path.exists(report_path)
    with open(report_path, "r") as f:
        content = f.read()
        assert "## 🏆 Top Signals" in content
        assert "## ⚠️ Disqualified Signals" in content
        assert "scam, spam" in content
        assert "Good signal" in content
        assert "Evidence:" in content
        assert "Validation Steps:" in content
        assert "Reasoning:" in content

@pytest.mark.asyncio
async def test_generate_report_no_signals_for_run(tmp_path):
    """Test fallback to top signals when run has no signals."""
    mock_store = MagicMock()
    mock_store.get_run = AsyncMock(return_value={"id": 1})
    mock_store.get_signals_for_run = AsyncMock(return_value=[])
    mock_store.get_top_signals = AsyncMock(return_value=[
        {"id": 1, "signal_summary": "Top signal", "total_score": 50, "disqualified": False}
    ])
    mock_store.get_stats = AsyncMock(return_value={"avg_score": 50})
    
    output_dir = tmp_path / "reports"
    report_path = await generate_report(mock_store, run_id=1, output_dir=str(output_dir))
    
    assert "Top signal" in open(report_path).read()

@pytest.mark.asyncio
async def test_generate_json_report(tmp_path):
    """Test generating a JSON report."""
    mock_store = MagicMock()
    mock_store.get_runs = AsyncMock(return_value=[{"id": 1}])
    mock_store.get_signals_for_run = AsyncMock(return_value=[
        {"id": 1, "signal_summary": "Test signal", "total_score": 40, "disqualified": False}
    ])
    mock_store.get_stats = AsyncMock(return_value={"avg_score": 40})
    
    output_dir = tmp_path / "reports"
    report_path = await generate_json_report(mock_store, run_id=None, output_dir=str(output_dir))
    
    assert os.path.exists(report_path)
    with open(report_path, "r") as f:
        data = json.load(f)
        assert data["run"]["id"] == 1
        assert data["ideas"][0]["signal_summary"] == "Test signal"
