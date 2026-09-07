# Contributing to DocuFlow AI

Thank you for contributing to **DocuFlow AI**! This guide outlines our development standards and contribution guidelines.

---

## 1. Development Workflow

1. Fork the repository and create a feature branch (`git checkout -b feat/my-feature`).
2. Follow **Clean Architecture** patterns:
   - Core business logic belongs in `backend/app/domain/`.
   - Use cases and orchestration belong in `backend/app/application/`.
   - External dependencies (DB, S3, Qdrant, Celery) belong in `backend/app/infrastructure/`.
   - HTTP routes and middleware belong in `backend/app/api/`.
3. Ensure all tests pass:
   ```bash
   # Backend
   cd backend
   pytest --cov=app --cov-report=term-missing
   ruff check app tests
   ruff format --check app tests
   mypy app

   # Frontend
   cd ../frontend
   npm test
   npm run lint
   npm run build
   ```

---

## 2. Commit Message Conventions

We adhere to the **Conventional Commits** specification:

- `feat:` A new feature for the user
- `fix:` A bug fix
- `docs:` Documentation-only changes
- `style:` Code style / formatting changes (no functional impact)
- `refactor:` Code refactoring without behavioral change
- `perf:` Performance improvements
- `test:` Adding or updating tests
- `build:` Build system or external dependency updates
- `ci:` Continuous integration configuration changes
- `chore:` Other non-production changes

---

## 3. Pull Request Guidelines

- Provide a clear description of the problem solved.
- Include unit/integration tests for any new functionality.
- Ensure all CI status checks pass.
