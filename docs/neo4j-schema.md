# Neo4j Knowledge Graph Schema
## Adaptive MAS-RCA

### 1. Node Labels

The knowledge graph contains five primary node labels.

| Node Label | Description | Required Properties |
|---|---|---|
| Incident | Represents a system incident or failure | incident_id, title, description, severity, timestamp, status |
| Service | Represents an application/service | service_id, name, description |
| Component | Represents a system component | component_id, name, type |
| RootCause | Represents the identified root cause | root_cause_id, description, category, confidence |
| Symptom | Represents an observed symptom | symptom_id, description, severity |

### 2. Relationship Types

| Relationship | From | To | Description |
|---|---|---|---|
| CAUSES | RootCause | Incident | Root cause produces an incident |
| AFFECTS | Incident | Service | Incident affects a service |
| RESOLVED_BY | Incident | RootCause | Incident is resolved by identifying the root cause |
| PART_OF | Service | Component | Service belongs to a system component |

### 3. Incident Properties

- incident_id: Unique incident identifier
- title: Short incident title
- description: Detailed description
- severity: Incident severity
- timestamp: Time when incident occurred
- status: Current incident status

### 4. Service Properties

- service_id: Unique service identifier
- name: Service name
- description: Service description

### 5. Component Properties

- component_id: Unique component identifier
- name: Component name
- type: Component type

### 6. RootCause Properties

- root_cause_id: Unique root cause identifier
- description: Description of root cause
- category: Root cause category
- confidence: Confidence score

### 7. Symptom Properties

- symptom_id: Unique symptom identifier
- description: Description of symptom
- severity: Symptom severity

### 8. Schema Validation

The implemented Neo4j database was validated using sample historical incidents.

Current node counts:

- Incident: 3
- Service: 2
- Component: 1
- RootCause: 2
- Symptom: 1

Total nodes: 9

Current relationship counts:

- AFFECTS: 3
- CAUSES: 3
- PART_OF: 2
- RESOLVED_BY: 3

Total relationships: 11

The schema is ready for ingestion scripts.