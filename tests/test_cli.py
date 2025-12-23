import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock, AsyncMock
from pain_radar.cli import app

runner = CliRunner()

def test_version():
    """Test the --version option."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "pain-radar" in result.stdout

def test_fetch_command_success():
    """Test the fetch command successfully calls run_fetch_only."""
    with patch("pain_radar.cli.fetch.get_settings") as mock_settings:
        # Setup settings
        settings = MagicMock()
        settings.db_path = ":memory:"
        settings.listing = "new"
        settings.posts_per_subreddit = 10
        settings.top_comments = 5
        settings.max_concurrency = 2
        settings.user_agent = "test-agent"
        mock_settings.return_value = settings

        with patch("pain_radar.cli.fetch.AsyncStore") as mock_store_cls:
            # Setup store
            mock_store = mock_store_cls.return_value
            mock_store.connect = AsyncMock()
            mock_store.close = AsyncMock()
            mock_store.get_all_active_subreddits = AsyncMock(return_value=["test_sub"])
            
            with patch("pain_radar.cli.fetch.run_fetch_only", new_callable=AsyncMock) as mock_run_fetch:
                mock_run_fetch.return_value = 5  # Returned 5 posts
                
                result = runner.invoke(app, ["fetch"])
                
                assert result.exit_code == 0
                assert "Fetched 5 posts" in result.stdout
                mock_run_fetch.assert_called_once()

def test_fetch_command_args():
    """Test fetch command with arguments."""
    with patch("pain_radar.cli.fetch.get_settings") as mock_settings:
        settings = MagicMock()
        settings.db_path = ":memory:"
        settings.listing = "new"
        settings.posts_per_subreddit = 10
        settings.top_comments = 5
        settings.max_concurrency = 2
        settings.user_agent = "test-agent"
        mock_settings.return_value = settings

        with patch("pain_radar.cli.fetch.AsyncStore") as mock_store_cls:
            with patch("pain_radar.cli.fetch.run_fetch_only", new_callable=AsyncMock) as mock_run_fetch:
                mock_run_fetch.return_value = 1
                
                result = runner.invoke(app, ["fetch", "-s", "specific_sub", "--limit", "20"])
                
                assert result.exit_code == 0
                assert "Fetching posts from 1 subreddits" in result.stdout
                
                # Check that arguments were passed to run_fetch_only via settings object
                call_args = mock_run_fetch.call_args
                fetch_settings = call_args[0][0]
                assert fetch_settings.subreddits == ["specific_sub"]
                assert fetch_settings.posts_per_subreddit == 20

def test_fetch_command_error():
    """Test fetch command error handling."""
    with patch("pain_radar.cli.fetch.get_settings") as mock_settings:
        settings = MagicMock()
        mock_settings.return_value = settings
        
        with patch("pain_radar.cli.fetch.AsyncStore") as mock_store_cls:
             mock_store = mock_store_cls.return_value
             mock_store.connect = AsyncMock()
             mock_store.close = AsyncMock()
             mock_store.get_all_active_subreddits = AsyncMock(return_value=["test"])

             with patch("pain_radar.cli.fetch.run_fetch_only", new_callable=AsyncMock) as mock_run_fetch:
                mock_run_fetch.side_effect = Exception("Fetch failed")
                
                result = runner.invoke(app, ["fetch"])
                
                assert result.exit_code == 1
                assert "Fetch failed" in result.stdout

def test_sources_list():
    """Test listing source sets."""
    with patch("pain_radar.cli.sources.get_settings") as mock_settings:
        settings = MagicMock()
        settings.db_path = ":memory:"
        mock_settings.return_value = settings

        with patch("pain_radar.cli.sources.AsyncStore") as mock_store_cls:
            mock_store = mock_store_cls.return_value
            mock_store.connect = AsyncMock()
            mock_store.close = AsyncMock()
            mock_store.get_source_sets = AsyncMock(return_value=[
                {"id": 1, "name": "Test Set", "subreddits": ["sub1"], "preset_key": "test"}
            ])
            
            result = runner.invoke(app, ["sources"])
            
            assert result.exit_code == 0
            assert "Test Set" in result.stdout
            assert "sub1" in result.stdout

def test_sources_add_preset():
    """Test adding a preset source set."""
    with patch("pain_radar.cli.sources.get_settings") as mock_settings:
        settings = MagicMock()
        settings.db_path = ":memory:"
        mock_settings.return_value = settings

        with patch("pain_radar.cli.sources.AsyncStore") as mock_store_cls:
            mock_store = mock_store_cls.return_value
            mock_store.connect = AsyncMock()
            mock_store.close = AsyncMock()
            mock_store.get_source_set_by_preset = AsyncMock(return_value=None)
            mock_store.create_source_set = AsyncMock(return_value=1)
            
            # Mock PRESETS
            with patch("pain_radar.cli.sources.PRESETS", {"indie_saas": {"name": "Indie SaaS", "subreddits": ["saas"], "description": "desc"}}):
                with patch("pain_radar.cli.sources.get_preset", return_value={"name": "Indie SaaS", "subreddits": ["saas"], "description": "desc"}):
                    result = runner.invoke(app, ["sources-add", "indie_saas"])
                    
                    assert result.exit_code == 0
                    assert "Added source set 'Indie SaaS'" in result.stdout
                    mock_store.create_source_set.assert_called_once()

def test_sources_add_custom():
    """Test adding a custom source set."""
    with patch("pain_radar.cli.sources.get_settings") as mock_settings:
        settings = MagicMock()
        settings.db_path = ":memory:"
        mock_settings.return_value = settings

        with patch("pain_radar.cli.sources.AsyncStore") as mock_store_cls:
            mock_store = mock_store_cls.return_value
            mock_store.connect = AsyncMock()
            mock_store.close = AsyncMock()
            mock_store.create_source_set = AsyncMock(return_value=2)
            
            result = runner.invoke(app, ["sources-add", "custom", "--subreddits", "sub1,sub2", "--name", "My Custom"])
            
            assert result.exit_code == 0
            assert "Added source set 'My Custom'" in result.stdout
            mock_store.create_source_set.assert_called_with(
                name="My Custom",
                subreddits=["sub1", "sub2"],
                description=None,
                preset_key=None
            )

def test_sources_remove():
    """Test removing a source set."""
    with patch("pain_radar.cli.sources.get_settings") as mock_settings:
        settings = MagicMock()
        settings.db_path = ":memory:"
        mock_settings.return_value = settings

        with patch("pain_radar.cli.sources.AsyncStore") as mock_store_cls:
            mock_store = mock_store_cls.return_value
            mock_store.connect = AsyncMock()
            mock_store.close = AsyncMock()
            mock_store.get_source_set = AsyncMock(return_value={"id": 1, "name": "Test Set"})
            mock_store.delete_source_set = AsyncMock()
            
            result = runner.invoke(app, ["sources-remove", "1"])
            
            assert result.exit_code == 0
            assert "Removed source set 'Test Set'" in result.stdout
            mock_store.delete_source_set.assert_called_with(1)

def test_help_all_commands():
    """Test that all subcommands show help successfully."""
    commands = [
        "fetch",
        "run",
        "sources",
        "sources-add",
        "sources-edit",
        "sources-remove",
        "init-db",
        "stats",
        "report",
        "runs",
        "top",
        "show",
        "export",
        "cluster",
        "digest",
        "reply-template",
        "alerts"  # alerts command group
    ]
    
    for cmd in commands:
        result = runner.invoke(app, [cmd, "--help"])
        assert result.exit_code == 0, f"Command {cmd} --help failed with exit code {result.exit_code}. Output: {result.stdout}"
        assert "Usage" in result.stdout
