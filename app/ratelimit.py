import time
from collections import deque


class LoginLimiter:
    """Bloqueia tentativas de login por IP + email.

    Fica em memoria, entao cada instancia conta separado. Em producao com varias
    instancias o lugar disso e um Redis.
    """

    def __init__(self, attempts: int, window_seconds: int):
        self.attempts = attempts
        self.window = window_seconds
        self.failures: dict[str, deque[float]] = {}

    def _recent(self, key: str, now: float) -> deque[float]:
        hits = self.failures.setdefault(key, deque())
        while hits and now - hits[0] > self.window:
            hits.popleft()
        return hits

    def blocked(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return len(self._recent(key, now)) >= self.attempts

    def fail(self, key: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if len(self.failures) > 10_000:
            self.failures.clear()
        self._recent(key, now).append(now)

    def reset(self, key: str) -> None:
        self.failures.pop(key, None)
