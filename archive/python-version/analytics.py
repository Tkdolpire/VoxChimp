"""
Notta Analytics Module

Privacy-first, opt-in analytics for understanding usage patterns.
No PII collected - only anonymized usage metrics.

Features:
- Opt-in by default (disabled until user consents)
- Anonymized device ID (SHA-256 hash of machine UUID)
- Local queue with persistence for offline support
- Batch sending with exponential backoff
- Graceful shutdown with queue flush
"""

import hashlib
import json
import logging
import os
import platform
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger('Notta.Analytics')

# Configuration
ANALYTICS_ENDPOINT = "https://notta-api.vercel.app/api/analytics"
QUEUE_FILE = Path.home() / '.notta_analytics_queue.json'
CONFIG_FILE = Path.home() / '.notta_config.json'

# Batching settings
BATCH_SIZE = 20
FLUSH_INTERVAL = 60  # seconds
MAX_QUEUE_SIZE = 500  # Max events to store locally
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # seconds, exponential backoff

# App version - should match Notta version
APP_VERSION = "1.0.0"


class Analytics:
    """Thread-safe analytics client with local queuing and batch sending."""

    _instance: Optional['Analytics'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'Analytics':
        """Singleton pattern for global analytics instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._enabled = False
        self._device_id: Optional[str] = None
        self._queue: list[dict] = []
        self._queue_lock = threading.Lock()
        self._flush_timer: Optional[threading.Timer] = None
        self._shutdown = False
        self._session_start: Optional[datetime] = None
        self._os_version = self._get_os_version()

        # Load existing queue
        self._load_queue()

        # Check if analytics is enabled in config
        self._load_enabled_state()

        # Generate device ID
        self._device_id = self._generate_device_id()

        logger.info(f"Analytics initialized (enabled={self._enabled})")

    def _generate_device_id(self) -> str:
        """Generate anonymized device ID from machine UUID."""
        try:
            # Try to get hardware UUID on macOS
            import subprocess
            result = subprocess.run(
                ['system_profiler', 'SPHardwareDataType'],
                capture_output=True,
                text=True,
                timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'Hardware UUID' in line:
                    uuid = line.split(':')[1].strip()
                    # Hash the UUID for privacy
                    return hashlib.sha256(uuid.encode()).hexdigest()
        except Exception as e:
            logger.debug(f"Could not get hardware UUID: {e}")

        # Fallback: use hostname + username hash
        try:
            import socket
            identifier = f"{socket.gethostname()}-{os.getenv('USER', 'unknown')}"
            return hashlib.sha256(identifier.encode()).hexdigest()
        except Exception:
            # Last resort: random but persistent ID
            id_file = Path.home() / '.notta_device_id'
            if id_file.exists():
                return id_file.read_text().strip()
            else:
                import secrets
                device_id = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
                try:
                    id_file.write_text(device_id)
                except Exception:
                    pass
                return device_id

    def _get_os_version(self) -> str:
        """Get macOS version string."""
        try:
            return f"macOS {platform.mac_ver()[0]}"
        except Exception:
            return f"{platform.system()} {platform.release()}"

    def _load_enabled_state(self):
        """Load analytics enabled state from config."""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self._enabled = config.get('analytics_enabled', False)
        except Exception as e:
            logger.debug(f"Could not load config: {e}")
            self._enabled = False

    def _load_queue(self):
        """Load persisted queue from disk."""
        try:
            if QUEUE_FILE.exists():
                with open(QUEUE_FILE, 'r') as f:
                    data = json.load(f)
                    with self._queue_lock:
                        self._queue = data.get('events', [])
                        # Trim if too large
                        if len(self._queue) > MAX_QUEUE_SIZE:
                            self._queue = self._queue[-MAX_QUEUE_SIZE:]
                    logger.debug(f"Loaded {len(self._queue)} queued events")
        except Exception as e:
            logger.debug(f"Could not load queue: {e}")

    def _save_queue(self):
        """Persist queue to disk."""
        try:
            with self._queue_lock:
                data = {'events': self._queue[-MAX_QUEUE_SIZE:]}
            with open(QUEUE_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.debug(f"Could not save queue: {e}")

    @property
    def enabled(self) -> bool:
        """Check if analytics is enabled."""
        return self._enabled

    def enable(self):
        """Enable analytics collection."""
        self._enabled = True
        self._save_config()
        self._start_flush_timer()
        logger.info("Analytics enabled")
        # Track the enablement
        self.track('settings_changed', {
            'setting': 'analytics_enabled',
            'old_value': False,
            'new_value': True
        })

    def disable(self):
        """Disable analytics collection."""
        # Track before disabling
        self.track('settings_changed', {
            'setting': 'analytics_enabled',
            'old_value': True,
            'new_value': False
        })
        self._flush_sync()  # Send any pending events
        self._enabled = False
        self._save_config()
        self._stop_flush_timer()
        logger.info("Analytics disabled")

    def _save_config(self):
        """Save analytics enabled state to config."""
        try:
            config = {}
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
            config['analytics_enabled'] = self._enabled
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save config: {e}")

    def track(self, event_type: str, data: Optional[dict[str, Any]] = None):
        """
        Track an analytics event.

        Args:
            event_type: Type of event (e.g., 'app_launch', 'recording_stop')
            data: Optional event-specific data (no PII!)
        """
        if not self._enabled:
            return

        event = {
            'event_type': event_type,
            'event_data': data or {},
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

        with self._queue_lock:
            self._queue.append(event)
            queue_size = len(self._queue)

        logger.debug(f"Tracked: {event_type} (queue size: {queue_size})")

        # Save queue and potentially flush
        self._save_queue()

        if queue_size >= BATCH_SIZE:
            self._flush_async()

    def start_session(self):
        """Mark the start of an app session."""
        self._session_start = datetime.utcnow()
        self.track('app_launch')
        self._start_flush_timer()

    def end_session(self):
        """Mark the end of an app session and flush events."""
        if self._session_start:
            duration_seconds = (datetime.utcnow() - self._session_start).total_seconds()
            self.track('session_end', {
                'duration_seconds': int(duration_seconds)
            })
        self._flush_sync()
        self._stop_flush_timer()

    def _start_flush_timer(self):
        """Start the periodic flush timer."""
        if self._flush_timer is not None:
            return

        def flush_periodically():
            if self._shutdown:
                return
            self._flush_async()
            if self._enabled and not self._shutdown:
                self._flush_timer = threading.Timer(FLUSH_INTERVAL, flush_periodically)
                self._flush_timer.daemon = True
                self._flush_timer.start()

        self._flush_timer = threading.Timer(FLUSH_INTERVAL, flush_periodically)
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def _stop_flush_timer(self):
        """Stop the periodic flush timer."""
        if self._flush_timer:
            self._flush_timer.cancel()
            self._flush_timer = None

    def _flush_async(self):
        """Flush events in a background thread."""
        thread = threading.Thread(target=self._flush_sync, daemon=True)
        thread.start()

    def _flush_sync(self):
        """Flush events synchronously with retry logic."""
        if not self._device_id:
            return

        with self._queue_lock:
            if not self._queue:
                return
            # Take up to BATCH_SIZE events
            batch = self._queue[:BATCH_SIZE]
            remaining = self._queue[BATCH_SIZE:]

        # Try to send
        success = self._send_batch(batch)

        if success:
            # Remove sent events from queue
            with self._queue_lock:
                # Re-check queue state in case new events were added
                self._queue = self._queue[len(batch):]
            self._save_queue()
            logger.debug(f"Flushed {len(batch)} events")

            # If more events remain, flush again
            with self._queue_lock:
                more_events = len(self._queue) >= BATCH_SIZE
            if more_events:
                self._flush_async()
        else:
            logger.debug("Flush failed, events remain queued")

    def _send_batch(self, events: list[dict]) -> bool:
        """Send a batch of events to the server with retry."""
        payload = {
            'device_id': self._device_id,
            'events': events,
            'app_version': APP_VERSION,
            'os_version': self._os_version
        }

        data = json.dumps(payload).encode('utf-8')

        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    ANALYTICS_ENDPOINT,
                    data=data,
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': f'Notta/{APP_VERSION}'
                    },
                    method='POST'
                )

                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        return True
                    else:
                        logger.debug(f"Analytics server returned {response.status}")

            except urllib.error.HTTPError as e:
                logger.debug(f"Analytics HTTP error: {e.code}")
                if e.code == 400:
                    # Bad request - don't retry, drop the events
                    logger.warning(f"Analytics rejected events: {e.read().decode()}")
                    return True  # Return true to drop bad events
            except urllib.error.URLError as e:
                logger.debug(f"Analytics network error: {e}")
            except Exception as e:
                logger.debug(f"Analytics error: {e}")

            # Exponential backoff before retry
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE ** (attempt + 1)
                time.sleep(delay)

        return False

    def shutdown(self):
        """Graceful shutdown - flush remaining events."""
        self._shutdown = True
        self._stop_flush_timer()
        if self._enabled:
            self._flush_sync()
        logger.info("Analytics shutdown complete")


# Global instance
_analytics: Optional[Analytics] = None


def get_analytics() -> Analytics:
    """Get the global analytics instance."""
    global _analytics
    if _analytics is None:
        _analytics = Analytics()
    return _analytics


def track(event_type: str, data: Optional[dict[str, Any]] = None):
    """Convenience function to track an event."""
    get_analytics().track(event_type, data)


def is_enabled() -> bool:
    """Check if analytics is enabled."""
    return get_analytics().enabled


def enable():
    """Enable analytics."""
    get_analytics().enable()


def disable():
    """Disable analytics."""
    get_analytics().disable()


def start_session():
    """Start an analytics session."""
    get_analytics().start_session()


def end_session():
    """End an analytics session."""
    get_analytics().end_session()


def shutdown():
    """Shutdown analytics gracefully."""
    get_analytics().shutdown()


# Consent dialog helper for PyObjC
def show_consent_dialog(callback: Callable[[bool], None]):
    """
    Show analytics consent dialog.
    Must be called from main thread with PyObjC available.

    Args:
        callback: Called with True if user consents, False otherwise
    """
    try:
        from AppKit import NSAlert, NSAlertStyleInformational

        alert = NSAlert.alloc().init()
        alert.setMessageText_("Help Improve Notta")
        alert.setInformativeText_(
            "Would you like to share anonymous usage data to help improve Notta?\n\n"
            "What we collect:\n"
            "- Feature usage (which buttons you use)\n"
            "- Performance metrics (transcription speed)\n"
            "- Error rates (what goes wrong)\n\n"
            "What we never collect:\n"
            "- Your audio recordings\n"
            "- Your transcribed text\n"
            "- Any personal information\n\n"
            "You can change this anytime in Settings."
        )
        alert.setAlertStyle_(NSAlertStyleInformational)
        alert.addButtonWithTitle_("Share Usage Data")
        alert.addButtonWithTitle_("No Thanks")

        response = alert.runModal()
        # 1000 = first button (Share), 1001 = second button (No Thanks)
        consented = response == 1000
        callback(consented)

    except ImportError:
        logger.warning("PyObjC not available for consent dialog")
        callback(False)
