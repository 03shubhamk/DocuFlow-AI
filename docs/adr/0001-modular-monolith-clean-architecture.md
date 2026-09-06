# ADR 0001: Modular Monolith with Clean Architecture

**Status:** Accepted  
**Date:** 2026-09-06  
**Deciders:** Principal Software Architect, Engineering Team  
**Consulted:** Backend Engineers, DevOps  
**Informed:** Stakeholders  

---

## 1. Context & Problem Statement

DocuFlow AI requires high cohesion between domain logic, document parsing, relational metadata, vector indexing, and presentation. Early-stage architectures frequently succumb to two extremes:
1. **Premature Microservices**: Splitting the system into separate services (auth service, doc service, parsing service, search service) introduces distributed transactions, network latency, complex gRPC/HTTP boilerplate, distributed tracing overhead, and operational friction.
2. **Coupled Spaghetti Monolith**: Placing business logic inside FastAPI route handlers or tight SQLAlchemy ORM callbacks leads to brittle, untestable code that is impossible to decompose later.

How should we structure the codebase to ensure rapid development, maximum testability, clean boundaries, and seamless future service extraction if necessary?

---

## 2. Decision Drivers

- **Developer Velocity**: Need for fast iteration without managing 5+ independent repositories or container deployments.
- **Maintainability & Testability**: Unit tests must run fast in-memory without starting live databases or web servers.
- **Clear Boundaries**: High cohesion within business modules and low coupling across infrastructure dependencies.
- **Future Decomposition Path**: Code should be decoupled so that any module (e.g., Document Ingestion) can be extracted into an independent microservice with zero changes to domain logic.

---

## 3. Considered Options

1. **Microservices Architecture** (Separate services for Auth, Ingestion, Storage, Vector Indexing).
2. **Standard Layered MVC Monolith** (Routers -> Controllers/Services -> Models).
3. **Modular Monolith with Clean Architecture (Hexagonal / Ports & Adapters)**.

---

## 4. Decision Outcome

**Chosen Option:** Option 3 — **Modular Monolith with Clean Architecture**.

We organize the backend into four concentric layers:
- **API Layer (`app/api/`)**: Thin FastAPI routers, schemas, and middlewares.
- **Application Layer (`app/application/`)**: Use cases orchestrating workflows.
- **Domain Layer (`app/domain/`)**: Pure business logic, entities, value objects, and abstract gateways (ports). Has zero third-party framework dependencies.
- **Infrastructure Layer (`app/infrastructure/`)**: Concrete adapters implementing ports (SQLAlchemy, MinIO, Qdrant, Docling, Celery).

### Positive Consequences
- **High Testability**: Domain and application use cases can be unit-tested in fractions of a second using mock gateway implementations.
- **Zero Framework Lock-in**: If we switch from FastAPI to another framework, or from SQLAlchemy to another ORM, the domain logic remains 100% untouched.
- **Operational Simplicity**: A single deployable backend artifact and unified database migration stream.
- **Effortless Future Extraction**: If document parsing or search requires isolated autoscaling, the adapter boundary allows clean extraction into a separate microservice.

### Negative Consequences
- Slightly more initial boilerplate (defining domain interfaces, DTOs, and adapters rather than directly invoking ORM models inside routes).
- Engineers must adhere to the dependency rule (dependencies point inwards). Linting rules (`flake8-import-restrictions` / `ruff`) will be enforced to prevent layer violations.
