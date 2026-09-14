import time

import pytest

from app.retrieval_cache import RetrievalCache


def test_cache_miss_and_set_then_hit():
    cache = RetrievalCache()

    result = [{"incident_id": "INC-005"}]

    assert cache.get(
        query="Database connection timeout",
        top_k=3,
    ) is None

    cache.set(
        query="Database connection timeout",
        top_k=3,
        value=result,
    )

    assert cache.get(
        query="Database connection timeout",
        top_k=3,
    ) == result


def test_query_normalization():
    cache = RetrievalCache()

    result = [{"incident_id": "INC-005"}]

    cache.set(
        query="Database   Connection   Timeout",
        top_k=3,
        value=result,
    )

    assert cache.get(
        query="  database connection timeout  ",
        top_k=3,
    ) == result


def test_top_k_is_part_of_cache_key():
    cache = RetrievalCache()

    result = [{"incident_id": "INC-005"}]

    cache.set(
        query="Database connection timeout",
        top_k=3,
        value=result,
    )

    assert cache.get(
        query="Database connection timeout",
        top_k=3,
    ) == result

    assert cache.get(
        query="Database connection timeout",
        top_k=5,
    ) is None


def test_cache_expires_after_ttl():
    cache = RetrievalCache(ttl_seconds=1)

    result = [{"incident_id": "INC-005"}]

    cache.set(
        query="Database connection timeout",
        top_k=3,
        value=result,
    )

    assert cache.get(
        query="Database connection timeout",
        top_k=3,
    ) == result

    time.sleep(1.1)

    assert cache.get(
        query="Database connection timeout",
        top_k=3,
    ) is None


def test_lru_eviction():
    cache = RetrievalCache(max_size=2)

    cache.set(
        query="query one",
        top_k=3,
        value=[{"incident_id": "INC-001"}],
    )

    cache.set(
        query="query two",
        top_k=3,
        value=[{"incident_id": "INC-002"}],
    )

    assert cache.get(
        query="query one",
        top_k=3,
    ) is not None

    cache.set(
        query="query three",
        top_k=3,
        value=[{"incident_id": "INC-003"}],
    )

    assert cache.get(
        query="query one",
        top_k=3,
    ) is not None

    assert cache.get(
        query="query two",
        top_k=3,
    ) is None

    assert cache.get(
        query="query three",
        top_k=3,
    ) is not None


def test_cache_clear():
    cache = RetrievalCache()

    cache.set(
        query="Database connection timeout",
        top_k=3,
        value=[{"incident_id": "INC-005"}],
    )

    assert cache.size() == 1

    cache.clear()

    assert cache.size() == 0


def test_invalid_cache_configuration():
    with pytest.raises(ValueError):
        RetrievalCache(max_size=0)

    with pytest.raises(ValueError):
        RetrievalCache(ttl_seconds=0)


def test_invalid_query():
    cache = RetrievalCache()

    with pytest.raises(ValueError):
        cache.get(
            query="",
            top_k=3,
        )

    with pytest.raises(TypeError):
        cache.get(
            query=None,
            top_k=3,
        )