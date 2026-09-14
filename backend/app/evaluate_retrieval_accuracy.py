import statistics
import time

from .hybrid_retrieval import retrieval


EVALUATION_SET = [
    {
        "query": (
            "The order service is experiencing database connection "
            "timeouts because it cannot obtain database connections."
        ),
        "expected_incident_id": "INC-005",
    },
    {
        "query": (
            "The order service is experiencing high latency because "
            "database queries are running slowly."
        ),
        "expected_incident_id": "INC-002",
    },
    {
        "query": (
            "The payment service is failing because the external "
            "payment provider is timing out."
        ),
        "expected_incident_id": "INC-003",
    },
    {
        "query": (
            "The database service has severe replica lag and read "
            "replicas are falling behind the primary."
        ),
        "expected_incident_id": "INC-017",
    },
    {
        "query": (
            "Order workers are failing to process messages because "
            "incoming message payloads are malformed."
        ),
        "expected_incident_id": "INC-020",
    },
]


TOP_K_VALUES = (1, 3, 5)


def evaluate_query(query: str, expected_incident_id: str, top_k: int):
    start = time.perf_counter()

    results = retrieval(
        query=query,
        top_k=top_k,
    )

    latency = time.perf_counter() - start

    retrieved_ids = [
        result["incident_id"]
        for result in results
    ]

    top_k_results = retrieved_ids[:top_k]

    hit = expected_incident_id in top_k_results

    rank = (
        top_k_results.index(expected_incident_id) + 1
        if hit
        else None
    )

    recall = 1.0 if hit else 0.0

    precision = (
        1.0 / top_k
        if hit
        else 0.0
    )

    return {
        "query": query,
        "expected_incident_id": expected_incident_id,
        "retrieved_ids": retrieved_ids,
        "hit": hit,
        "rank": rank,
        "recall": recall,
        "precision": precision,
        "latency_seconds": latency,
    }


def evaluate_top_k(top_k: int):
    results = []

    for item in EVALUATION_SET:
        result = evaluate_query(
            query=item["query"],
            expected_incident_id=item["expected_incident_id"],
            top_k=top_k,
        )

        results.append(result)

    recall_at_k = statistics.mean(
        result["recall"]
        for result in results
    )

    precision_at_k = statistics.mean(
        result["precision"]
        for result in results
    )

    hit_rate = statistics.mean(
        1.0 if result["hit"] else 0.0
        for result in results
    )

    average_latency = statistics.mean(
        result["latency_seconds"]
        for result in results
    )

    return {
        "top_k": top_k,
        "recall_at_k": recall_at_k,
        "precision_at_k": precision_at_k,
        "hit_rate": hit_rate,
        "average_latency_seconds": average_latency,
        "results": results,
    }


def print_report(report):
    print()
    print("=" * 70)
    print(f"RETRIEVAL ACCURACY REPORT - TOP-{report['top_k']}")
    print("=" * 70)

    print(
        f"Recall@{report['top_k']}: "
        f"{report['recall_at_k']:.2%}"
    )

    print(
        f"Precision@{report['top_k']}: "
        f"{report['precision_at_k']:.2%}"
    )

    print(
        f"Hit rate: "
        f"{report['hit_rate']:.2%}"
    )

    print(
        f"Average latency: "
        f"{report['average_latency_seconds']:.4f}s"
    )

    print()
    print("Individual queries:")

    for index, result in enumerate(
        report["results"],
        start=1,
    ):
        status = "PASS" if result["hit"] else "MISS"

        print()
        print(f"{index}. [{status}]")
        print(
            f"   Expected: "
            f"{result['expected_incident_id']}"
        )
        print(
            f"   Retrieved: "
            f"{result['retrieved_ids']}"
        )
        print(
            f"   Rank: "
            f"{result['rank']}"
        )
        print(
            f"   Latency: "
            f"{result['latency_seconds']:.4f}s"
        )


def main():
    print("=" * 70)
    print("HYBRID RETRIEVAL ACCURACY BENCHMARK")
    print("=" * 70)

    for top_k in TOP_K_VALUES:
        report = evaluate_top_k(top_k)
        print_report(report)


if __name__ == "__main__":
    main()