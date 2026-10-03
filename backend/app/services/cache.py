"""Bounded per-key single-flight loading for synchronous read-only caches."""
from functools import lru_cache, wraps
from threading import RLock


def singleflight_cache(maxsize: int):
    def decorate(function):
        cached = lru_cache(maxsize=maxsize)(function)
        # Fixed lock stripes avoid a growing lock registry as users select runs.
        locks = tuple(RLock() for _ in range(32))

        @wraps(function)
        def wrapped(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            with locks[hash(key) % len(locks)]:
                return cached(*args, **kwargs)

        wrapped.cache_clear = cached.cache_clear
        wrapped.cache_info = cached.cache_info
        return wrapped
    return decorate
