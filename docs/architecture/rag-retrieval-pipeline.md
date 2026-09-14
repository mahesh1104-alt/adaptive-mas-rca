# RAG Retrieval Pipeline Architecture

**Project:** Adaptive Multi-Agent Root Cause Analysis System  
**Phase:** Phase 5 — Knowledge Base (RAG: Vector DB + Knowledge Graph)  
**Subtask:** 33 — Design the RAG Retrieval Pipeline Architecture  
**Status:** Design Specification  
**Version:** 1.0

---

## 1. Purpose

This document defines the Retrieval-Augmented Generation (RAG) pipeline architecture for the Adaptive Multi-Agent Root Cause Analysis system.

The purpose of the RAG pipeline is to retrieve relevant historical incident knowledge and operational relationships for a current incident. The retrieved information is provided as evidence to the downstream multi-agent diagnosis and Large Language Model (LLM) reasoning components.

The RAG architecture combines:

- Preprocessed incident features
- Text embeddings
- ChromaDB vector similarity search
- Neo4j knowledge graph traversal
- Result merging and deduplication
- Re-ranking
- Token-budgeted context construction

This document defines the retrieval architecture before implementation of the ChromaDB indexing and hybrid retrieval modules.

---

## 2. Design Goals

The RAG pipeline has the following goals:

1. Retrieve historical incidents that are semantically similar to the current incident.
2. Use knowledge-graph relationships to provide operational and causal context.
3. Combine vector and graph evidence into one ranked retrieval result.
4. Preserve source identifiers so retrieved evidence remains traceable.
5. Prevent duplicate evidence from appearing in the final context.
6. Respect the token budget of the downstream LLM prompt.
7. Keep retrieval parameters configurable.
8. Allow graceful degradation when one retrieval source is temporarily unavailable.
9. Provide evidence that can support explainable root-cause diagnosis.

---

## 3. Position in the Overall System

The RAG pipeline is positioned after preprocessing and feature extraction and before specialized-agent analysis and LLM reasoning.

The high-level system flow is:

```text
Cloud Observability Sources
        |
        v
Logs / Metrics / Traces / Alerts / Source Code
        |
        v
Preprocessing
        |
        v
Feature Extraction and Noise Reduction
        |
        v
Current Incident Feature Bundle
        |
        v
RAG Retrieval Pipeline
        |
        +--------------------+
        |                    |
        v                    v
   Embedding           Incident Entities
        |                    |
        v                    v
    ChromaDB               Neo4j
 Vector Similarity      Graph Traversal
        |                    |
        +---------+----------+
                  |
                  v
         Merge + Deduplicate
                  |
                  v
              Re-ranking
                  |
                  v
         Token Budget Filter
                  |
                  v
           Final RAG Context
                  |
                  v
        Multi-Agent Diagnosis
                  |
                  v
            LLM Reasoning
```

The RAG layer therefore acts as a knowledge retrieval layer between incident analysis and final reasoning.

---

## 4. Input to the RAG Pipeline

The input to the retrieval pipeline is a compact feature bundle produced by the preprocessing and feature-extraction stages.

The feature bundle may contain:

- Incident summary
- Affected service
- Important log messages
- Error codes
- Metric anomalies
- Trace errors
- Trace bottlenecks
- Relevant source-code snippets
- Alert information
- Time information
- Failure or symptom information

The feature bundle is preferred over raw observability data because preprocessing removes noise and reduces redundant information before retrieval.

### Example Feature Bundle

```text
Incident:
Payment requests are returning HTTP 500 errors.

Affected service:
payment-service

Log evidence:
Database connection failed

Metric evidence:
Connection pool utilization increased sharply.

Trace evidence:
payment-service database span is slow and failing.

Alert:
High payment error rate

Source evidence:
Database connection handling code near the failing function.
```

The feature bundle provides the high-signal information required to construct an effective retrieval query.

---

## 5. Query Construction

The feature bundle is converted into a retrieval query.

The query should emphasize high-signal information such as:

- Incident description
- Affected service
- Error messages
- Error codes
- Metric anomaly descriptions
- Trace failure or bottleneck information
- Relevant failure mode
- Relevant source-code context

Low-signal information such as repetitive log lines and irrelevant timestamps should not dominate the query.

The resulting query is then passed to the embedding generation module.

### Query Construction Flow

```text
Feature Bundle
      |
      v
Relevant Feature Selection
      |
      v
Retrieval Query Text
      |
      v
Embedding Generation
```

The query should be compact enough to avoid unnecessary information while retaining the important characteristics of the incident.

---

## 6. Embedding Generation

The retrieval query generated from the incident feature bundle is converted into a numerical vector representation using the project's embedding generation component.

The embedding represents the semantic meaning of the current incident and is used to identify historically similar incidents stored in ChromaDB.

### Embedding Flow

```text
Retrieval Query Text
        |
        v
Embedding Generation
        |
        v
Query Embedding Vector
        |
        v
ChromaDB Similarity Search
```

The embedding process should use the same embedding model and compatible vector representation used when indexing historical incident documents.

The generated embedding should contain the important semantic information about the incident rather than unnecessary raw observability data.

---

## 7. Vector Retrieval — ChromaDB

ChromaDB is used as the vector database for semantic retrieval of historically similar incidents.

The query embedding is compared against embeddings stored in ChromaDB.

The vector retrieval stage returns the most semantically similar historical incident records.

### Initial Vector Retrieval Configuration

| Parameter | Initial Value | Description |
|---|---:|---|
| `VECTOR_TOP_K` | 10 | Maximum number of vector candidates retrieved |
| Similarity metric | Configured by embedding store | Used to compare query and stored embeddings |
| Metadata filtering | Enabled | Restricts results using incident metadata where applicable |

The value `VECTOR_TOP_K = 10` is an initial configurable design choice. It can be adjusted during implementation and evaluation.

### Vector Retrieval Flow

```text
Current Incident
      |
      v
Retrieval Query
      |
      v
Query Embedding
      |
      v
ChromaDB
      |
      v
Top-K Similar Incidents
      |
      v
Vector Evidence
```

Each retrieved result should preserve sufficient metadata for later merging and ranking.

Expected information includes:

- Incident identifier
- Document identifier
- Retrieved content
- Similarity score
- Affected service
- Failure mode
- Severity
- Source reference
- Relevant metadata

---

## 8. Graph Retrieval — Neo4j

Neo4j is used to retrieve operational and causal relationships associated with the current incident.

The graph retrieval stage uses entities identified from the current incident, such as:

- Incident
- Service
- Component
- RootCause
- Symptom

Relevant relationships may include:

- `CAUSES`
- `AFFECTS`
- `RESOLVED_BY`
- `PART_OF`

### Initial Graph Traversal Configuration

| Parameter | Initial Value | Description |
|---|---:|---|
| `GRAPH_MAX_HOPS` | 2 | Maximum relationship depth explored |
| Entity types | Incident, Service, Component, RootCause, Symptom | Primary retrieval entities |
| Relationship types | CAUSES, AFFECTS, RESOLVED_BY, PART_OF | Relevant operational relationships |

The maximum hop count is an initial configurable design choice.

### Graph Retrieval Flow

```text
Current Incident Features
          |
          v
Entity Identification
          |
          v
Neo4j Graph Query
          |
          v
Relevant Nodes and Relationships
          |
          v
Graph Evidence
```

Graph retrieval provides information that may not be captured by semantic similarity alone.

For example, a historically similar incident may identify the same service, component, or root cause even when the wording of the current incident is different.

---

## 9. Hybrid Retrieval Flow

The RAG pipeline combines vector similarity evidence and knowledge-graph evidence.

The complete retrieval flow is:

```text
                  Current Incident
                         |
                         v
                 Feature Bundle
                         |
                         v
                Query Construction
                         |
                         v
                 Embedding Generation
                         |
              +----------+----------+
              |                     |
              v                     v
          ChromaDB                Neo4j
       Vector Retrieval       Graph Retrieval
              |                     |
              v                     v
        Vector Evidence       Graph Evidence
              |                     |
              +----------+----------+
                         |
                         v
                Merge + Deduplicate
                         |
                         v
                    Re-ranking
                         |
                         v
                 Token Budget Filter
                         |
                         v
                  Final RAG Context
```

The vector database provides semantic similarity, while the knowledge graph provides relationship-based operational context.

The two retrieval paths are therefore complementary rather than interchangeable.

---

## 10. Result Merging

Results returned by ChromaDB and Neo4j are merged into a common retrieval-result structure.

Each result should contain enough information to identify:

- Evidence source
- Source identifier
- Incident or document identifier
- Retrieved content
- Vector relevance score, when available
- Graph relevance score, when available
- Service or component information
- Failure or root-cause information
- Metadata

### Deduplication

Duplicate evidence should be removed before final ranking.

The preferred deduplication key is:

```text
incident_id
```

If an incident identifier is not available, a stable document or source identifier should be used.

The purpose of deduplication is to prevent the same historical incident from consuming multiple positions and unnecessary tokens in the final LLM context.

---

## 11. Re-ranking Strategy

After vector and graph results are merged and deduplicated, the candidates are re-ranked according to their combined relevance.

The initial ranking strategy is:

```text
final_score =
    0.70 * vector_score
    +
    0.30 * graph_score
```

The initial weights are configurable design parameters.

### Ranking Interpretation

- **Vector score** represents semantic similarity between the current incident and historical evidence.
- **Graph score** represents the relevance of relationships discovered through the knowledge graph.
- **Final score** determines the final evidence ordering.

When one retrieval source is unavailable, the available evidence can be ranked using its available relevance information instead of failing the complete retrieval operation.

The ranking strategy can be refined during later implementation and evaluation based on retrieval quality.

---

## 12. Metadata and Filtering

Metadata is preserved throughout the retrieval pipeline so that retrieved evidence can be filtered and traced.

Potential metadata includes:

- `incident_id`
- `document_id`
- `service`
- `component`
- `severity`
- `failure_mode`
- `timestamp`
- `source_type`
- `root_cause`
- `source_reference`

Metadata filtering may be applied before or during retrieval when the current incident provides reliable filtering information.

For example:

```text
Current service = payment-service
        |
        v
Prefer evidence associated with payment-service
```

Filtering should not remove potentially useful cross-service evidence when relationships indicate that another service or component may be relevant to the incident.

---

## 13. Token-Budget Constraints

The final retrieved evidence must fit within a defined context budget for downstream LLM reasoning.

The initial RAG retrieval context budget is:

```text
RAG_CONTEXT_TOKEN_BUDGET = 8000
```

This value is configurable.

The token budget applies to the retrieved evidence supplied to the downstream reasoning stage.

### Token Budget Flow

```text
Merged Retrieval Results
          |
          v
       Ranking
          |
          v
Highest-Relevance Evidence
          |
          v
Token Budget Check
          |
     +----+----+
     |         |
   Within    Exceeds
   Budget    Budget
     |         |
     |         v
     |    Remove lowest-
     |    ranked evidence
     |         |
     +----<----+
          |
          v
Final RAG Context
```

If the retrieved evidence exceeds the available budget, the lowest-ranked evidence is removed first.

High-relevance and high-confidence evidence should therefore receive priority in the final context.

---

## 14. Final RAG Context Structure

The final RAG context should provide structured evidence to the downstream multi-agent diagnosis system.

A conceptual structure is:

```text
RAG Context
|
+-- Current Incident
|
+-- Similar Historical Incidents
|     |
|     +-- Incident A
|     +-- Incident B
|     +-- Incident C
|
+-- Graph Relationships
|     |
|     +-- Service relationships
|     +-- Component relationships
|     +-- Root-cause relationships
|
+-- Supporting Evidence
|     |
|     +-- Logs
|     +-- Metrics
|     +-- Traces
|     +-- Source references
|
+-- Evidence Metadata
      |
      +-- Source identifiers
      +-- Relevance scores
      +-- Service
      +-- Failure mode
```

The context should contain evidence rather than instructions.

Retrieved historical text, logs, source-code snippets, and other external content must be treated as untrusted evidence and not as system-level instructions.

---

## 15. Evidence Traceability

Every retrieved evidence item should retain a source reference.

This allows the diagnosis system to identify where supporting evidence originated.

The retrieval result should therefore preserve:

```text
Evidence
   |
   +-- Source Type
   +-- Source ID
   +-- Incident ID
   +-- Document ID
   +-- Relevance Score
   +-- Retrieved Content
```

Traceability supports explainable root-cause analysis because an agent can associate a diagnosis with the historical or operational evidence used to support it.

---

## 16. Failure and Fallback Handling

The retrieval pipeline should degrade gracefully when one of its knowledge sources is unavailable.

### ChromaDB Unavailable

If ChromaDB retrieval fails:

```text
Current Incident
      |
      +----X ChromaDB
      |
      v
    Neo4j
      |
      v
Graph Evidence
```

The system should continue using available graph evidence.

### Neo4j Unavailable

If Neo4j retrieval fails:

```text
Current Incident
      |
      +----X Neo4j
      |
      v
   ChromaDB
      |
      v
Vector Evidence
```

The system should continue using available vector evidence.

### Both Sources Unavailable

If both retrieval sources are unavailable, the system should continue with the current incident evidence when sufficient evidence is available.

The retrieval failure should be explicitly recorded so that downstream components know that historical retrieval was unavailable.

---

## 17. Security and Trust Boundary

Retrieved information is external evidence and must not be treated as trusted instructions.

This applies to:

- Historical incident descriptions
- Logs
- Source-code snippets
- Error messages
- Graph properties
- Stored operational notes

The RAG context must maintain a clear separation between system or agent instructions and retrieved evidence.

```text
System / Agent Instructions
            |
            X
            |
Retrieved Evidence
```

Retrieved content must not be allowed to override system instructions, agent instructions, security policies, or access-control requirements.

Sensitive information should only be retrieved when the requesting workflow is authorized to access it.

---

## 18. Configuration Parameters

The following parameters are defined as initial configurable values:

| Parameter | Value | Purpose |
|---|---:|---|
| `VECTOR_TOP_K` | 10 | Number of vector candidates |
| `GRAPH_MAX_HOPS` | 2 | Maximum graph traversal depth |
| `VECTOR_WEIGHT` | 0.70 | Weight of vector relevance |
| `GRAPH_WEIGHT` | 0.30 | Weight of graph relevance |
| `RAG_CONTEXT_TOKEN_BUDGET` | 8000 | Maximum retrieved-context budget |

These values are design defaults rather than experimentally validated optimum values.

They should be configurable so that retrieval quality can be evaluated and tuned during later implementation.

---

## 19. End-to-End Example

Consider the following current incident:

```text
Payment requests are returning HTTP 500 errors.
Database connections are failing.
Connection pool utilization is unusually high.
Database spans are slow and failing.
```

The retrieval pipeline processes the incident as follows:

```text
Incident Feature Bundle
        |
        v
Query Construction
        |
        v
"payment service database connection failure
 high connection pool utilization"
        |
        v
Embedding
        |
        +----------------------+
        |                      |
        v                      v
    ChromaDB                 Neo4j
        |                      |
        v                      v
Similar Incidents       Related Services/
                        Components/Root Causes
        |                      |
        +----------+-----------+
                   |
                   v
             Merge Results
                   |
                   v
              Deduplicate
                   |
                   v
                Re-rank
                   |
                   v
          Apply Token Budget
                   |
                   v
             Final RAG Context
```

The final context can then be supplied to the specialized diagnosis agents and LLM reasoning components.

---

## 20. Requirements Traceability

The RAG design supports the project requirements as follows:

| Requirement | RAG Design Support |
|---|---|
| Multi-source analysis | Feature bundle combines logs, metrics, traces, alerts and source evidence |
| Historical knowledge | ChromaDB retrieves similar historical incidents |
| Relationship-based reasoning | Neo4j provides service, component and causal relationships |
| Semantic retrieval | Embedding-based ChromaDB search |
| Explainability | Source identifiers and evidence metadata are preserved |
| Relevance | Vector and graph scores are combined |
| Configurability | Retrieval parameters are configurable |
| LLM reasoning | Final RAG context is supplied to downstream reasoning |
| Security | Retrieved content is treated as untrusted evidence |
| Continuous learning | Historical incident knowledge can be incorporated into the knowledge base |
| Multi-agent diagnosis | Retrieved evidence is provided to downstream agents |

---

## 21. Implementation Mapping

This design maps to the upcoming implementation subtasks:

| Design Component | Implementation Subtask |
|---|---|
| Feature bundle | Existing preprocessing and feature-extraction components |
| Embedding generation | Existing embedding-generation component |
| ChromaDB indexing and search | Subtask 34 |
| Neo4j population | Subtask 35 |
| Hybrid retrieval | Subtask 36 |
| RAG context formatting | Subtask 37 |
| LangChain retriever | Subtask 38 |
| Retrieval caching | Subtask 39 |

The implementation should follow this architecture unless later testing identifies a requirement or technical constraint that requires a design change.

---

## 22. Expected Retrieval Contract

The hybrid retrieval pipeline should conceptually return a collection of ranked evidence items.

Each evidence item should contain:

```text
EvidenceItem
|
+-- source_type
+-- source_id
+-- incident_id
+-- document_id
+-- content
+-- vector_score
+-- graph_score
+-- final_score
+-- service
+-- component
+-- failure_mode
+-- metadata
```

The exact Python data structure will be defined during implementation.

The important design requirement is that retrieval results remain structured, ranked, deduplicated and traceable.

---

## 23. Design Decisions Summary

The following decisions are established for the initial implementation:

1. Use the preprocessed incident feature bundle as the retrieval input.
2. Construct a compact high-signal retrieval query.
3. Generate an embedding from the retrieval query.
4. Use ChromaDB for semantic similarity retrieval.
5. Retrieve an initial maximum of 10 vector candidates.
6. Use Neo4j for relationship-based retrieval.
7. Use a maximum initial graph traversal depth of 2 hops.
8. Merge vector and graph evidence.
9. Deduplicate evidence using stable incident or document identifiers.
10. Re-rank using configurable vector and graph weights.
11. Use an initial vector weight of 0.70.
12. Use an initial graph weight of 0.30.
13. Limit the final retrieved context to an initial budget of 8,000 tokens.
14. Preserve source identifiers for traceability.
15. Gracefully degrade when one retrieval source is unavailable.
16. Treat retrieved content as untrusted evidence.

---

## 24. Subtask 33 Completion Criteria

Subtask 33 is considered complete when:

- [x] RAG retrieval flow is documented.
- [x] Query construction is defined.
- [x] Embedding generation stage is defined.
- [x] ChromaDB vector retrieval is defined.
- [x] Neo4j graph retrieval is defined.
- [x] Top-K retrieval strategy is defined.
- [x] Result merging and deduplication are defined.
- [x] Re-ranking strategy is defined.
- [x] Token-budget constraints are defined.
- [x] Failure and fallback behavior is defined.
- [x] Evidence traceability is defined.
- [x] Security boundary is defined.
- [x] Configuration parameters are defined.
- [x] Mapping to upcoming implementation subtasks is defined.

**Expected Result:** A reviewed RAG retrieval architecture is available for implementation in Subtasks 34–39.
