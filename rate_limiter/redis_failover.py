"""Automatic Redis failover: detect primary failure and promote replica."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RedisFailoverManager:
    """Monitors Redis primary and automatically promotes replica on failure.
    
    This manager runs a background thread that periodically checks if the
    primary Redis is healthy. If it fails and a replica is configured,
    it automatically promotes the replica to primary.
    """

    def __init__(
        self,
        primary_url: str,
        replica_url: str,
        check_interval_sec: float = 5.0,
        failure_threshold: int = 3,
        on_failover: Callable[[], None] | None = None,
    ) -> None:
        """Initialize Redis failover manager.

        Args:
            primary_url: Redis primary URL (e.g., redis://localhost:6379/0)
            replica_url: Redis replica URL (e.g., redis://localhost:6380/0)
            check_interval_sec: How often to check primary health (seconds)
            failure_threshold: Number of consecutive failures before promoting
            on_failover: Callback function when failover happens
        """
        self.primary_url = primary_url
        self.replica_url = replica_url
        self.check_interval_sec = check_interval_sec
        self.failure_threshold = failure_threshold
        self.on_failover = on_failover or (lambda: None)

        self._primary_client = redis.from_url(primary_url)
        self._replica_client = redis.from_url(replica_url)

        self._consecutive_failures = 0
        self._is_monitoring = False
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start background monitoring thread."""
        with self._lock:
            if self._is_monitoring:
                logger.warning("Failover manager already running")
                return

            self._is_monitoring = True
            self._monitor_thread = threading.Thread(
                target=self._monitor_primary, daemon=True
            )
            self._monitor_thread.start()
            logger.info(
                f"Redis failover manager started (check every {self.check_interval_sec}s)"
            )

    def stop(self) -> None:
        """Stop background monitoring thread."""
        with self._lock:
            self._is_monitoring = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
            logger.info("Redis failover manager stopped")

    def _monitor_primary(self) -> None:
        """Background thread: check primary health and promote replica if needed."""
        while self._is_monitoring:
            try:
                time.sleep(self.check_interval_sec)
                if not self._is_primary_healthy():
                    self._consecutive_failures += 1
                    logger.warning(
                        f"Primary health check failed ({self._consecutive_failures}/{self.failure_threshold})"
                    )

                    if self._consecutive_failures >= self.failure_threshold:
                        self._promote_replica()
                else:
                    # Primary is healthy, reset counter
                    if self._consecutive_failures > 0:
                        logger.info("Primary recovered, resetting failure counter")
                    self._consecutive_failures = 0

            except Exception as e:
                logger.error(f"Error in failover monitor: {e}")

    def _is_primary_healthy(self) -> bool:
        """Check if primary Redis is responding."""
        try:
            return bool(self._primary_client.ping())
        except (RedisError, OSError, ConnectionError):
            return False

    def _promote_replica(self) -> None:
        """Promote replica to primary (SLAVEOF NO ONE)."""
        try:
            logger.critical("Promoting Redis replica to primary!")
            self._replica_client.execute_command("SLAVEOF", "NO", "ONE")
            logger.critical("Replica promoted successfully")

            # Call failover callback (may trigger circuit breaker probe, etc.)
            self.on_failover()

            # Stop monitoring since we now have a new primary
            self._is_monitoring = False

        except Exception as e:
            logger.error(f"Failed to promote replica: {e}")
            # Keep trying on next interval

    def close(self) -> None:
        """Clean up resources."""
        self.stop()
        self._primary_client.close()
        self._replica_client.close()
