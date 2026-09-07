# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

---

## Reporting a Vulnerability

We take the security of **DocuFlow AI** seriously. If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public issue on GitHub.
2. Email the core security team at `security@docuflow.ai` with details:
   - Type of issue (e.g. buffer overflow, SQL injection, privilege escalation, cross-site scripting)
   - Step-by-step instructions to reproduce the issue
   - Affected components and versions
   - Potential impact
3. We will acknowledge receipt within 24 hours and provide regular progress updates until a resolution is deployed.

---

## Security Best Practices in DocuFlow AI

- **Multi-Tenant Isolation**: Row-Level Security and explicit `tenant_id` filtering on all database queries.
- **Secret Management**: JWT secrets, MinIO credentials, and database passwords loaded exclusively via environment variables.
- **Container Hardening**: All Docker images run as non-root unprivileged users.
- **Request Validation**: Strict Pydantic input schemas and MIME-type verification on file uploads.
