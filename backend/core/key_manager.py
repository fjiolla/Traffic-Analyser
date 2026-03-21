"""
Key Manager — Thread-safe round-robin API key rotation.
Parses comma-separated key lists from env vars and rotates on each call.
Falls back to primary key if no backup keys are available.
"""
from __future__ import annotations

import os
import threading


class _KeyRotator:
    """Thread-safe round-robin key rotator."""

    def __init__(self, primary_env: str, pool_env: str):
        self._lock = threading.Lock()
        primary = os.getenv(primary_env, "")
        pool_csv = os.getenv(pool_env, "")
        pool_keys = [k.strip() for k in pool_csv.split(",") if k.strip()] if pool_csv else []
        # Primary first, then pool keys
        self._keys: list[str] = []
        if primary:
            self._keys.append(primary)
        for k in pool_keys:
            if k not in self._keys:
                self._keys.append(k)
        self._index = 0

    def next(self) -> str:
        """Return the next key in round-robin order."""
        if not self._keys:
            return ""
        with self._lock:
            key = self._keys[self._index % len(self._keys)]
            self._index += 1
            return key

    @property
    def available(self) -> bool:
        return len(self._keys) > 0


_groq_rotator: _KeyRotator | None = None
_gemini_rotator: _KeyRotator | None = None
_init_lock = threading.Lock()


def _ensure_init():
    global _groq_rotator, _gemini_rotator
    if _groq_rotator is None:
        with _init_lock:
            if _groq_rotator is None:
                _groq_rotator = _KeyRotator("GROQ_API_KEY", "GROQ_API_KEYS")
                _gemini_rotator = _KeyRotator("GOOGLE_AI_API_KEY", "GOOGLE_AI_API_KEYS")


def get_groq_key() -> str:
    """Get next Groq API key (round-robin)."""
    _ensure_init()
    assert _groq_rotator is not None
    return _groq_rotator.next()


def get_gemini_key() -> str:
    """Get next Gemini API key (round-robin)."""
    _ensure_init()
    assert _gemini_rotator is not None
    return _gemini_rotator.next()
