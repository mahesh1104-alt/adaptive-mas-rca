# Knowledge Base Update Procedure

## 1. Purpose

This document describes how a newly resolved incident is incrementally
added to the RCA knowledge base.

The update process stores the incident in both:

- ChromaDB for vector similarity retrieval
- Neo4j for graph-based causal retrieval

## 2. Update Flow

```text
Resolved Incident
       |
       v
Validate incident
       |
       v
Generate historical incident text
       |
       v
Generate embedding
       |
       +--------------------+
       |                    |
       v                    v
   ChromaDB               Neo4j
       |                    |
       |              Incident node
       |              Service node
       |              RootCause node
       |                    |
       |              AFFECTS / CAUSES /
       |              RESOLVED_BY
       |                    |
       +---------+----------+
                 |
                 v
       Knowledge base updated