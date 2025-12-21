import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pain_radar.cluster import Clusterer
from pain_radar.models import Cluster, ClusterItem

@pytest.mark.asyncio
async def test_cluster_signals_success(sample_cluster_item):
    """Test successful clustering of signals."""
    # Setup expected result
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

    # Mock the chain creation and invocation
    # Clusterer.cluster_items does: chain = prompt | structured_llm; result = await chain.ainvoke(...)
    # We can patch ChatPromptTemplate to return a mock that when or-ed returns our mock chain.
    with patch("pain_radar.cluster.ChatPromptTemplate.from_messages") as mock_from_messages:
        mock_prompt = MagicMock()
        mock_from_messages.return_value = mock_prompt
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        
        # prompt | structured_llm -> mock_prompt.__or__(...)
        mock_prompt.__or__.return_value = mock_chain

        with patch("pain_radar.cluster.settings") as mock_settings:
            mock_settings.openai_api_key.get_secret_value.return_value = "fake-key"
            with patch("pain_radar.cluster.ChatOpenAI"):
                clusterer = Clusterer()
                results = await clusterer.cluster_items([sample_cluster_item])

                # Verify
                assert len(results) == 1
                assert results[0].title == "Test Cluster"
                mock_chain.ainvoke.assert_called_once()

@pytest.mark.asyncio
async def test_cluster_signals_empty():
    """Test clustering with empty input."""
    with patch("pain_radar.cluster.settings") as mock_settings:
        mock_settings.openai_api_key.get_secret_value.return_value = "fake-key"
        with patch("pain_radar.cluster.ChatOpenAI"):
            clusterer = Clusterer()
            results = await clusterer.cluster_items([])
            assert results == []

@pytest.mark.asyncio
async def test_cluster_signals_error(sample_cluster_item):
    """Test handling of errors during clustering."""
    with patch("pain_radar.cluster.ChatPromptTemplate.from_messages") as mock_from_messages:
        mock_prompt = MagicMock()
        mock_from_messages.return_value = mock_prompt
        mock_chain = AsyncMock()
        mock_chain.ainvoke.side_effect = Exception("Clustering failed")
        mock_prompt.__or__.return_value = mock_chain

        with patch("pain_radar.cluster.settings") as mock_settings:
            mock_settings.openai_api_key.get_secret_value.return_value = "fake-key"
            with patch("pain_radar.cluster.ChatOpenAI"):
                clusterer = Clusterer()
                results = await clusterer.cluster_items([sample_cluster_item])
                assert results == []
