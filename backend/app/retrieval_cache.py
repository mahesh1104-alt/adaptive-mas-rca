import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock


logger = logging.getLogger(__name__)


CACHE_TTL_SECONDS = 300
CACHE_MAX_SIZE = 128


@dataclass
class CacheEntry:
    value: list[dict]
    created_at: float


class RetrievalCache:
    """
    Thread-safe in-memory LRU cache with TTL expiration.
    """

    def __init__(
        self,
        max_size: int = CACHE_MAX_SIZE,
        ttl_seconds: int = CACHE_TTL_SECONDS,
    ):
        if max_size < 1:
            raise ValueError("max_size must be at least 1")

        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")

        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()

    @staticmethod
    def _normalize_query(query: str) -> str:
        if not isinstance(query, str):
            raise TypeError("query must be a string")

        if not query.strip():
            raise ValueError("query cannot be empty")

        return " ".join(query.lower().split())

    def _make_key(
        self,
        query: str,
        top_k: int,
    ) -> str:
        normalized_query = self._normalize_query(query)

        raw_key = (
            f"query={normalized_query}|"
            f"top_k={top_k}"
        )

        return hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()

    def get(
        self,
        query: str,
        top_k: int,
    ) -> list[dict] | None:
        key = self._make_key(
            query=query,
            top_k=top_k,
        )

        now = time.monotonic()

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                logger.info(
                    "Retrieval cache MISS"
                )
                return None

            if now - entry.created_at >= self.ttl_seconds:
                del self._cache[key]

                logger.info(
                    "Retrieval cache EXPIRED"
                )
                return None

            self._cache.move_to_end(key)

            logger.info(
                "Retrieval cache HIT"
            )

            return entry.value

    def set(
        self,
        query: str,
        top_k: int,
        value: list[dict],
    ) -> None:
        key = self._make_key(
            query=query,
            top_k=top_k,
        )

        with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.monotonic(),
            )

            self._cache.move_to_end(key)

            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._cache)


retrieval_cache = RetrievalCache()


def cached_retrieval(
    query: str,
    top_k: int,
    retrieval_function,
) -> list[dict]:
    """
    Return cached retrieval results when available.

    On a cache miss, execute retrieval_function, cache the result,
    and return it.
    """
    cached_result = retrieval_cache.get(
        query=query,
        top_k=top_k,
    )

    if cached_result is not None:
        return cached_result

    result = retrieval_function(
        query=query,
        top_k=top_k,
    )

    retrieval_cache.set(
        query=query,
        top_k=top_k,
        value=result,
    )

    return result