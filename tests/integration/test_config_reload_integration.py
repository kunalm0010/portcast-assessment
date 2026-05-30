"""Integration tests for config reloading."""

from pathlib import Path

import pytest

from rate_limiter.config_reloader import ConfigReloader
from rate_limiter.limiter import RateLimiter
from rate_limiter.models import LimiterOutcome

pytestmark = pytest.mark.integration


def test_limiter_respects_config_reload(tmp_path: Path, rate_limit_config, redis_store):
    """Test that limiter uses updated config after reload."""
    # Create test config files
    limits_file = tmp_path / "limits.yaml"
    clients_file = tmp_path / "clients.yaml"
    
    limits_file.write_text("""
tiers:
  free:
    default:
      rate_per_sec: 10
      burst: 2
""")
    
    clients_file.write_text("""
clients:
  test-client: free
""")
    
    # Create limiter with initial config
    initial_config = rate_limit_config
    limiter = RateLimiter(initial_config, redis_store)
    
    # Create config reloader
    reloader = ConfigReloader(
        limits_file,
        clients_file,
        on_reload=limiter.set_config,
    )
    
    # Initial burst should be 20 (from default config)
    # Make 1 request to establish state
    result = limiter.allow("client-free-1", "GET /v1/demo")
    assert result.outcome == LimiterOutcome.ALLOWED
    
    # Now reload config with new burst=2
    reloader.reload_config()
    
    # Next request should use new config
    # Since burst is now 2, we should be able to make 2 requests before hitting limit
    for _ in range(1):
        result = limiter.allow("test-client", "GET /v1/test")
        assert result.outcome == LimiterOutcome.ALLOWED
    
    # Should be rate limited on 3rd request (burst=2)
    result = limiter.allow("test-client", "GET /v1/test")
    result = limiter.allow("test-client", "GET /v1/test")
    assert result.outcome == LimiterOutcome.RATE_LIMITED


def test_reload_count_increments(tmp_path: Path):
    """Test that reload count increments on each reload."""
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
    
    reloader = ConfigReloader(limits_file, clients_file)
    
    assert reloader.reload_count == 0
    
    reloader.reload_config()
    assert reloader.reload_count == 1
    
    reloader.reload_config()
    assert reloader.reload_count == 2
    
    reloader.reload_config()
    assert reloader.reload_count == 3
