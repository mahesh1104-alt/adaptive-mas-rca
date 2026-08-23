# Subtask 15: Backend API Contract

## OpenAPI Specification

The Adaptive MAS-RCA backend API is defined using
OpenAPI 3.0.3.

The specification is located at:

`api/openapi.yaml`

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /incidents | Create an incident |
| GET | /incidents | Retrieve incidents |
| GET | /incidents/{incident_id} | Retrieve a specific incident |
| POST | /diagnose | Perform root cause analysis |
| POST | /feedback | Submit RCA feedback |
| POST | /auth/login | Authenticate a user |
| GET | /dashboard | Retrieve dashboard statistics |

## Validation

The OpenAPI specification was validated using
Swagger Editor.

The specification successfully generated interactive
API documentation and displayed the request and response
schemas.

## Frontend Integration

The OpenAPI specification serves as the shared contract
between the backend and frontend teams.

The frontend can implement API calls based on the
request and response schemas without waiting for the
backend implementation to be completed.