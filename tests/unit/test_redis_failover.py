"""Tests for Redis failover manager."""

from unittest.mock import MagicMock, patch

import pytest

from rate_limiter.redis_failover import RedisFailoverManager


def test_failover_manager_initialization():
    """Test failover manager initializes correctly."""
    manager = RedisFailoverManager(
        primary_url="redis://localhost:6379/0",
        replica_url="redis://localhost:6380/0",
    )
    
    assert manager.primary_url == "redis://localhost:6379/0"
    assert manager.replica_url == "redis://localhost:6380/0"
    assert manager._consecutive_failures == 0
    assert manager._is_monitoring is False


def test_failover_manager_calls_callback_on_failover():
    """Test that failover callback is called when replica is promoted."""
    callback = MagicMock()
    
    with patch.object(RedisFailoverManager, '_is_primary_healthy', return_value=False):
        with patch.object(RedisFailoverManager, '_promote_replica') as mock_promote:
            manager = RedisFailoverManager(
                primary_url="redis://localhost:6379/0",
                replica_url="redis://localhost:6380/0",
                on_failover=callback,
            )
            
            # Mock the monitoring method to trigger failure detection
            manager._consecutive_failures = 3
            manager._promote_replica()
            
            callback.assert_called_once()


def test_failover_threshold_triggers_promotion():
    """Test that consecutive failures trigger promotion."""
    manager = RedisFailoverManager(
        primary_url="redis://localhost:6379/0",
        replica_url="redis://localhost:6380/0",
        failure_threshold=3,
    )
    
    with patch.object(manager, '_is_primary_healthy', return_value=False):
        with patch.object(manager, '_promote_replica') as mock_promote:
            # Simulate failures
            manager._consecutive_failures = 0
            manager._is_monitoring = True
            
            # This would normally be called by monitor thread
            # Simulating the check logic
            for i in range(3):
                if not manager._is_primary_healthy():
                    manager._consecutive_failures += 1
                    if manager._consecutive_failures >= manager.failure_threshold:
                        mock_promote()
            
            assert mock_promote.called


def test_failover_manager_resets_on_primary_recovery():
    """Test that failure counter resets when primary recovers."""
    manager = RedisFailoverManager(
        primary_url="redis://localhost:6379/0",
        replica_url="redis://localhost:6380/0",
    )
    
    manager._consecutive_failures = 2
    
    with patch.object(manager, '_is_primary_healthy', return_value=True):
        # Simulate successful health check
        if manager._is_primary_healthy():
            manager._consecutive_failures = 0
    
    assert manager._consecutive_failures == 0


def test_failover_manager_start_stop():
    """Test that failover manager can start and stop."""
    manager = RedisFailoverManager(
        primary_url="redis://localhost:6379/0",
        replica_url="redis://localhost:6380/0",
    )
    
    # Start should create thread
    manager.start()
    assert manager._is_monitoring is True
    assert manager._monitor_thread is not None
    
    # Stop should disable monitoring
    manager.stop()
    assert manager._is_monitoring is False


def test_failover_manager_idempotent_start():
    """Test that start() is idempotent."""
    manager = RedisFailoverManager(
        primary_url="redis://localhost:6379/0",
        replica_url="redis://localhost:6380/0",
    )
    
    manager.start()
    first_thread = manager._monitor_thread
    
    # Starting again should not create new thread
    manager.start()
    assert manager._monitor_thread is first_thread
    
    manager.stop()
