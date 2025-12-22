import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pain_radar.cluster import Clusterer
from pain_radar.models import Cluster, ClusterItem

@pytest.mark.asyncio
async def test_cluster_signals_success(sample_cluster_item, mock_llm):
    """Test successful clustering of signals."""
    expected_cluster = Cluster(
        title="Test Cluster",
        summary="Test Summary",
        target_audience="Test Audience",
        why_it_matters="Test Importance",
        signal_ids=[sample_cluster_item.id],
        quotes=["Quote 1"],
        urls=[sample_cluster_item.url]
    )
    mock_response = {"clusters": [expected_cluster.model_dump()]}

    # Patch ChatPromptTemplate.from_messages to control the chain
    with patch("pain_radar.cluster.ChatPromptTemplate.from_messages") as mock_from_messages:
        mock_prompt = MagicMock()
        mock_from_messages.return_value = mock_prompt
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        mock_prompt.__or__.return_value = mock_chain

        clusterer = Clusterer(llm=mock_llm)
        results = await clusterer.cluster_items([sample_cluster_item])

        assert len(results) == 1
        assert results[0].title == "Test Cluster"
        mock_chain.ainvoke.assert_called_once()

@pytest.mark.asyncio
async def test_cluster_signals_empty():
    """Test clustering with empty input."""
    clusterer = Clusterer(llm=MagicMock())
    results = await clusterer.cluster_items([])
    assert results == []

@pytest.mark.asyncio
async def test_cluster_signals_error(sample_cluster_item, mock_llm):
    """Test handling of errors during clustering."""
    with patch("pain_radar.cluster.ChatPromptTemplate.from_messages") as mock_from_messages:
        mock_prompt = MagicMock()
        mock_from_messages.return_value = mock_prompt
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.side_effect = Exception("Clustering failed")
        mock_prompt.__or__.return_value = mock_chain

        clusterer = Clusterer(llm=mock_llm)
        results = await clusterer.cluster_items([sample_cluster_item])
        assert results == []
