import time

from .hybrid_retrieval import retrieval
from .retrieval_cache import RetrievalCache


QUERY = (
    "Database connection attempts are timing out "
    "and the order service cannot obtain database connections"
)

TOP_K = 3
ITERATIONS = 5


def benchmark_uncached():
    times = []

    for _ in range(ITERATIONS):
        start = time.perf_counter()

        retrieval(
            query=QUERY,
            top_k=TOP_K,
        )

        times.append(
            time.perf_counter() - start
        )

    return times


def benchmark_cached():
    cache = RetrievalCache()

    times = []

    def cached_retrieval():
        cached = cache.get(
            query=QUERY,
            top_k=TOP_K,
        )

        if cached is not None:
            return cached

        result = retrieval(
            query=QUERY,
            top_k=TOP_K,
        )

        cache.set(
            query=QUERY,
            top_k=TOP_K,
            value=result,
        )

        return result

    for _ in range(ITERATIONS):
        start = time.perf_counter()

        cached_retrieval()

        times.append(
            time.perf_counter() - start
        )

    return times


def average(values):
    return sum(values) / len(values)


def main():
    print("=" * 60)
    print("RETRIEVAL CACHE BENCHMARK")
    print("=" * 60)

    uncached_times = benchmark_uncached()
    cached_times = benchmark_cached()

    uncached_average = average(uncached_times)
    cached_average = average(cached_times)

    print()
    print(
        f"Uncached average: "
        f"{uncached_average:.4f} seconds"
    )

    print(
        f"Cached average:   "
        f"{cached_average:.4f} seconds"
    )

    if cached_average > 0:
        speedup = (
            uncached_average / cached_average
        )

        print(
            f"Average speedup:   "
            f"{speedup:.2f}x"
        )

    print()
    print("Uncached timings:")

    for index, value in enumerate(
        uncached_times,
        start=1,
    ):
        print(
            f"  Run {index}: {value:.4f}s"
        )

    print()
    print("Cached timings:")

    for index, value in enumerate(
        cached_times,
        start=1,
    ):
        print(
            f"  Run {index}: {value:.4f}s"
        )


if __name__ == "__main__":
    main()