# Adaptive MAS RCA — System Requirements

**Project:** Adaptive Multi-Agent Root Cause Analysis (Adaptive MAS RCA)

**Document ID:** REQ-001

**Version:** 1.0.0

**Status:** Draft for Review

**Date:** 2026-08-19

---

## 1. Purpose

This document defines the functional and non-functional requirements
for the Adaptive MAS RCA system.

The system is designed to perform automated Root Cause Analysis (RCA)
using multiple cooperating AI agents, multi-source incident data,
knowledge graphs, vector search, feedback, and explainable diagnosis.

---

## 2. System Scope

The Adaptive MAS RCA system will:

- Ingest incident information from multiple sources.
- Normalize and correlate incident data.
- Coordinate multiple specialized diagnostic agents.
- Generate root-cause hypotheses.
- Retrieve relevant historical and technical evidence.
- Use a knowledge graph to represent relationships between entities.
- Use vector search for semantic retrieval.
- Rank and validate root-cause hypotheses.
- Provide explainable RCA results.
- Capture user feedback.
- Improve future diagnosis through a feedback loop.
- Provide a dashboard for monitoring and RCA visualization.

---

# 3. Functional Requirements

## FR-01 — Multi-Source Data Ingestion

The system shall ingest incident and operational data from multiple
sources such as:

- Application logs
- Infrastructure logs
- Database events
- Monitoring alerts
- Deployment information
- Incident/ticket data
- Historical RCA records

The ingestion component shall normalize incoming data into a common
internal representation.

---

## FR-02 — Incident Normalization

The system shall transform heterogeneous incident information into a
standardized incident representation containing relevant fields such
as:

- Incident ID
- Timestamp
- Service
- Severity
- Error information
- Logs
- Metrics
- Deployment information
- Related entities

---

## FR-03 — Multi-Agent Diagnosis

The system shall support multiple specialized diagnostic agents.

Examples include:

- Log Analysis Agent
- Metrics Analysis Agent
- Dependency Analysis Agent
- Knowledge Graph Agent
- Historical RCA Agent
- Hypothesis/Reasoning Agent

Agents shall be capable of contributing evidence and hypotheses to the
overall RCA process.

---

## FR-04 — Agent Coordination

The system shall coordinate diagnostic agents through an orchestration
mechanism.

The orchestration layer shall:

- Assign tasks to agents.
- Collect agent outputs.
- Manage execution order or parallel execution.
- Combine evidence.
- Handle agent failures.
- Produce a consolidated diagnosis.

---

## FR-05 — Root-Cause Hypothesis Generation

The system shall generate one or more possible root-cause hypotheses
for an incident.

Each hypothesis shall contain:

- Root-cause description
- Supporting evidence
- Confidence score
- Related services/components
- Contributing factors

---

## FR-06 — Knowledge Graph Integration

The system shall maintain relationships between relevant system
entities using a graph database.

The knowledge graph shall support relationships such as:

- Service depends on service
- Service produces log
- Deployment affects service
- Incident affects service
- Error originates from component

Neo4j shall be used as the initial graph database.

---

## FR-07 — Vector-Based Semantic Retrieval

The system shall store and retrieve vector representations of relevant
incident and RCA information.

The vector database shall support:

- Embedding storage
- Similarity search
- Historical incident retrieval
- Semantic evidence retrieval

ChromaDB shall be used as the initial vector database.

---

## FR-08 — Historical RCA Retrieval

The system shall retrieve similar historical incidents and previous
root-cause analyses.

Retrieved historical information shall be provided as supporting
evidence for diagnosis.

---

## FR-09 — Evidence Aggregation

The system shall aggregate evidence obtained from:

- Agents
- Logs
- Historical incidents
- Knowledge graph
- Vector search
- Monitoring data

The aggregated evidence shall be associated with the generated
hypotheses.

---

## FR-10 — Root-Cause Ranking

The system shall rank candidate root causes according to available
evidence and confidence.

The system shall provide:

- Top-1 root cause
- Top-3 root causes
- Confidence scores
- Supporting evidence

---

## FR-11 — Explainable RCA

The system shall provide an explanation for each diagnosis.

The explanation shall identify:

- Why the root cause was selected.
- Which evidence supports it.
- Which agents contributed to the conclusion.
- Relevant system dependencies.
- Confidence level.

---

## FR-12 — Feedback Loop

The system shall allow users or operators to provide feedback on RCA
results.

Feedback may include:

- Correct diagnosis
- Incorrect diagnosis
- Missing evidence
- Additional root cause
- Explanation quality

The feedback shall be stored for future analysis and system improvement.

---

## FR-13 — RCA Dashboard

The system shall provide a dashboard displaying:

- Active incidents
- Incident severity
- Root-cause predictions
- Confidence scores
- Evidence
- Agent contributions
- RCA history
- Feedback information

---

## FR-14 — Health Monitoring

The system shall provide health-check endpoints for system services.

The backend shall expose a health-check endpoint that confirms service
availability.

---

## FR-15 — Authentication and Authorization

The system shall support authentication and role-based authorization
for protected functionality.

Different user roles may have different permissions for:

- Viewing incidents
- Running RCA
- Providing feedback
- Managing system configuration
- Viewing administrative information

---

# 4. Non-Functional Requirements

## NFR-01 — Performance

The system should provide RCA results within an acceptable response
time for normal incident workloads.

Target latency shall be measured during system evaluation.

---

## NFR-02 — Scalability

The system shall be designed to support increasing:

- Number of incidents
- Number of agents
- Number of users
- Volume of logs
- Historical RCA records
- Vector embeddings

Individual services should be independently scalable where possible.

---

## NFR-03 — Availability

The system should remain available when individual non-critical
components fail.

The architecture should support service health checks and graceful
failure handling.

---

## NFR-04 — Reliability

The system shall handle:

- Agent failures
- Database connection failures
- Invalid input
- Missing evidence
- Partial data
- Temporary service failures

without causing complete system failure where recovery is possible.

---

## NFR-05 — Explainability

RCA results shall be traceable to the evidence used during diagnosis.

The system shall avoid producing root-cause conclusions without
providing supporting evidence.

---

## NFR-06 — Security

The system shall protect:

- Authentication credentials
- Database credentials
- API keys
- Incident information
- System configuration

Secrets shall not be committed to source control.

---

## NFR-07 — Maintainability

The system shall use modular components so that agents, data sources,
databases, and services can be independently modified or replaced.

---

## NFR-08 — Observability

The system shall provide sufficient logging and monitoring to diagnose
failures in:

- Backend services
- Agent execution
- Database connections
- API requests
- RCA workflows

---

## NFR-09 — Data Persistence

Important application data shall persist across service restarts.

PostgreSQL, Neo4j, and ChromaDB shall use persistent storage.

---

## NFR-10 — Portability

The system shall be deployable using Docker and Docker Compose to reduce
environment-specific configuration problems.

---

## NFR-11 — Usability

The RCA dashboard shall present diagnosis, evidence, confidence, and
explanations in a clear and understandable manner.

---

## NFR-12 — Extensibility

The system shall allow new agents, data sources, retrieval methods, and
analysis modules to be added without major changes to the existing
architecture.

---

# 5. Initial Technology Constraints

| Component | Technology |
|---|---|
| Backend | Python / FastAPI |
| Frontend | React / Vite |
| Relational Database | PostgreSQL |
| Knowledge Graph | Neo4j |
| Vector Database | ChromaDB |
| Containerization | Docker |
| Orchestration | Docker Compose |
| Version Control | Git / GitHub |

---

# 6. Initial Quality Targets

The following metrics will be measured during later implementation and
evaluation:

| Metric | Purpose |
|---|---|
| Top-1 RCA Accuracy | Correctness of highest-ranked root cause |
| Top-3 RCA Accuracy | Whether correct root cause appears in top three |
| Evidence Coverage | Amount of diagnosis supported by evidence |
| Confidence Calibration | Reliability of confidence scores |
| Explanation Completeness | Quality of RCA explanations |
| Diagnosis Latency | Time required to generate diagnosis |
| MTTR Proxy | Estimated reduction in diagnosis/recovery time |

Exact measurement formulas will be defined during the evaluation and
metrics-design phase.

---

# 7. Assumptions

- Required development tools are available.
- Docker is available for local deployment.
- PostgreSQL, Neo4j, and ChromaDB are available through the configured
  development environment.
- Incident data will be available in a suitable format for testing.
- AI/ML models may be replaced or upgraded during development.

---

# 8. Out of Scope

The initial version does not guarantee:

- Fully autonomous production remediation.
- Automatic modification of production infrastructure.
- Guaranteed identification of every possible root cause.
- Elimination of human review for high-impact incidents.

The system focuses primarily on automated diagnosis and explainable
root-cause analysis.

---

# 9. Requirements Traceability

| Requirement Group | Planned Component |
|---|---|
| FR-01 to FR-02 | Ingestion / normalization |
| FR-03 to FR-04 | Multi-agent orchestration |
| FR-05 | RCA reasoning |
| FR-06 | Neo4j knowledge graph |
| FR-07 to FR-08 | ChromaDB retrieval |
| FR-09 to FR-11 | Evidence and explanation |
| FR-12 | Feedback service |
| FR-13 | React dashboard |
| FR-14 | FastAPI health service |
| FR-15 | Authentication service |
| NFR-01 to NFR-12 | Architecture and evaluation |

---

# 10. Review and Approval

**Document Version:** 1.0.0

**Status:** Draft for Review

The requirements document shall be circulated to the project guide/team
for review.

Review comments shall be incorporated before the document is marked
approved.

After approval, the document version shall be updated and committed to
the project repository.

---

# 11. Version History

| Version | Date | Status | Description |
|---|---|---|---|
| 1.0.0 | 2026-08-19 | Draft | Initial functional and non-functional requirements |