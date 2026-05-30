"""Handle config reload on SIGHUP signal."""

from __future__ import annotations

import logging
import signal
from pathlib import Path
from typing import Callable

from rate_limiter.config import RateLimitConfig

logger = logging.getLogger(__name__)


class ConfigReloader:
    """Handles hot-reloading of rate limit config on SIGHUP signal.
    
    When the process receives SIGHUP (hangup signal), it reloads the
    limits.yaml and clients.yaml files without restarting the API.
    """

    def __init__(
        self,
        limits_path: Path,
        clients_path: Path,
        on_reload: Callable[[RateLimitConfig], None] | None = None,
    ) -> None:
        """Initialize config reloader.

        Args:
            limits_path: Path to limits.yaml
            clients_path: Path to clients.yaml
            on_reload: Callback function when config is reloaded
        """
        self.limits_path = limits_path
        self.clients_path = clients_path
        self.on_reload = on_reload or (lambda config: None)
        self._reload_count = 0

    def setup_signal_handler(self) -> None:
        """Setup SIGHUP signal handler."""
        signal.signal(signal.SIGHUP, self._handle_sighup)
        logger.info("Config reloader: SIGHUP handler registered")

    def _handle_sighup(self, signum: int, frame) -> None:
        """Signal handler for SIGHUP."""
        logger.info("Received SIGHUP, reloading config...")
        try:
            self.reload_config()
        except Exception as e:
            logger.error(f"Failed to reload config on SIGHUP: {e}")

    def reload_config(self) -> RateLimitConfig:
        """Reload config from disk and trigger callback."""
        try:
            new_config = RateLimitConfig.load(self.limits_path, self.clients_path)
            self._reload_count += 1
            logger.info(
                f"Config reloaded successfully (reload #{self._reload_count}): "
                f"{len(new_config.known_client_ids())} clients"
            )
            self.on_reload(new_config)
            return new_config
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            raise

    @property
    def reload_count(self) -> int:
        """Number of times config has been reloaded."""
        return self._reload_count
