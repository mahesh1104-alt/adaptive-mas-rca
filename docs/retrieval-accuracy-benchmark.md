# Retrieval Accuracy Benchmark

## 1. Purpose

This benchmark evaluates whether the hybrid ChromaDB + Neo4j retriever
surfaces the known correct historical incident for representative incident
queries.

The evaluation uses historical incidents with known correct matches.

## 2. Evaluation Set

| Query focus | Expected incident |
|---|---|
| Order-service database connection timeout | INC-005 |
| Order-service slow database queries | INC-002 |
| Payment provider timeout | INC-003 |
| Database replica lag | INC-017 |
| Malformed order-worker message payloads | INC-020 |

## 3. Evaluation Method

For each query:

1. Execute the hybrid retriever.
2. Retrieve the ranked historical incidents.
3. Check whether the expected incident appears in the top-k results.
4. Record the rank of the expected incident.
5. Calculate Recall@k and Precision@k.
6. Record retrieval latency.

The evaluation was performed for k = 1, 3, and 5.

## 4. Results

| Metric | Top-1 | Top-3 | Top-5 |
|---|---:|---:|---:|
| Recall@k | 100.00% | 100.00% | 100.00% |
| Precision@k | 100.00% | 33.33% | 20.00% |
| Hit rate | 100.00% | 100.00% | 100.00% |
| Average latency | 0.0793s | 0.0756s | 0.0705s |

## 5. Individual Results

| Query | Expected | Rank | Result |
|---|---|---:|---|
| Database connection timeout | INC-005 | 1 | PASS |
| Slow database queries | INC-002 | 1 | PASS |
| Payment provider timeout | INC-003 | 1 | PASS |
| Database replica lag | INC-017 | 1 | PASS |
| Malformed message payloads | INC-020 | 1 | PASS |

## 6. Analysis

All five expected historical incidents were retrieved at rank 1.

The hybrid retriever therefore achieved 100% Recall@1 on this evaluation set.
Increasing k to 3 or 5 did not improve recall because the correct incident was
already ranked first for every query.

Precision decreases as k increases because additional relevant or related
historical incidents are included alongside the single known correct match.

## 7. Tuning Decision

No retrieval tuning was made based on this benchmark.

The current hybrid retrieval configuration was retained because all five
evaluation queries successfully identified the expected historical incident
as the highest-ranked result.

## 8. Limitations

This is a representative sample benchmark rather than a statistically
comprehensive evaluation of all possible incidents.

The evaluation set contains five queries and one known correct historical
match per query. Future evaluation should expand the dataset and include
ambiguous, noisy, and previously unseen incident descriptions.

## 9. Conclusion

The benchmark confirms that the current hybrid retriever successfully
surfaces relevant historical incidents for the tested incident scenarios,
with 100% Recall@1 and all expected matches ranked first.