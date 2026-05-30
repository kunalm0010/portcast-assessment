"""Tests for config reloader."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rate_limiter.config_reloader import ConfigReloader


@pytest.fixture
def config_paths(tmp_path: Path):
    """Create temporary config files."""
    limits_file = tmp_path / "limits.yaml"
    clients_file = tmp_path / "clients.yaml"
    
    limits_file.write_text("""
tiers:
  free:
    default:
      rate_per_sec: 10
      burst: 20
""")
    
    clients_file.write_text("""
clients:
  client-free-1: free
""")
    
    return limits_file, clients_file


def test_config_reloader_loads_config(config_paths):
    """Test that config reloader loads config."""
    limits_path, clients_path = config_paths
    reloader = ConfigReloader(limits_path, clients_path)
    
    config = reloader.reload_config()
    
    assert config is not None
    assert "client-free-1" in config.known_client_ids()


def test_config_reloader_increments_reload_count(config_paths):
    """Test that reload count increments."""
    limits_path, clients_path = config_paths
    reloader = ConfigReloader(limits_path, clients_path)
    
    assert reloader.reload_count == 0
    reloader.reload_config()
    assert reloader.reload_count == 1
    reloader.reload_config()
    assert reloader.reload_count == 2


def test_config_reloader_calls_callback(config_paths):
    """Test that reload callback is called."""
    limits_path, clients_path = config_paths
    callback = MagicMock()
    reloader = ConfigReloader(limits_path, clients_path, on_reload=callback)
    
    reloader.reload_config()
    
    callback.assert_called_once()
    # Verify callback received a config object
    args = callback.call_args[0]
    assert len(args) == 1
    config = args[0]
    assert "client-free-1" in config.known_client_ids()


def test_config_reloader_handles_invalid_file(tmp_path: Path):
    """Test that reloader handles missing files gracefully."""
    nonexistent = tmp_path / "nonexistent.yaml"
    
    reloader = ConfigReloader(nonexistent, nonexistent)
    
    with pytest.raises(Exception):
        reloader.reload_config()


def test_config_reloader_updates_with_new_client(config_paths):
    """Test that reloader picks up new clients."""
    limits_path, clients_path = config_paths
    reloader = ConfigReloader(limits_path, clients_path)
    
    # First reload
    config1 = reloader.reload_config()
    assert len(config1.known_client_ids()) == 1
    
    # Add new client
    clients_path.write_text("""
clients:
  client-free-1: free
  client-standard-1: standard
""")
    
    # Second reload
    config2 = reloader.reload_config()
    assert len(config2.known_client_ids()) == 2
    assert "client-standard-1" in config2.known_client_ids()


@patch('signal.signal')
def test_config_reloader_registers_sighup_handler(mock_signal, config_paths):
    """Test that SIGHUP handler is registered."""
    limits_path, clients_path = config_paths
    reloader = ConfigReloader(limits_path, clients_path)
    
    reloader.setup_signal_handler()
    
    # Verify signal.signal was called
    mock_signal.assert_called_once()
    import signal
    assert mock_signal.call_args[0][0] == signal.SIGHUP
