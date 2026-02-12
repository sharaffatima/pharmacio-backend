# Pharmacio Backend

Backend service for the Pharmacio Smart Pharmacy System.
This repository contains the core business logic, APIs, and data management for pharmacy operations, including file intake, OCR result handling, proposal generation, approval workflows, inventory & capital updates, monitoring, and access control.

It acts as the **source of truth for business logic** and coordinates with:

- a shared AI/OCR Engine
- a separate Frontend application
- persistent storage (database + file storage)

## Responsibilities of the Backend

The backend is responsible for:

- Accepting and registering uploaded warehouse offer files (PDFs)
- Dispatching OCR requests to the AI/OCR Engine
- Receiving, validating, and storing structured OCR results
- Managing inventory, sales history, and capital data
- Generating purchase proposals based on offers and internal data
- Enforcing approval workflows and business rules
- Updating inventory and capital only after approval
- Monitoring stock levels and creating alerts
- Enforcing role-based access control (RBAC)

## System Context

- Each pharmacy runs its own backend instance and database
- The AI/OCR Engine is a shared external service
- Communication with AI is asynchronous and job-based
- The backend is the source of truth for business state

## Architecture Overview

- Architecture style: Modular Monolith
- Deployment scope: One backend per pharmacy
- Scalability model: Scale per pharmacy, not globally
- Async operations: Job-based dispatch for OCR integration

### Core internal modules include:

- Authentication & RBAC
- File intake & metadata
- OCR result handling
- Proposal & approval workflow
- Inventory & capital management
- Monitoring & notifications

## Tech Stack

- Language: Python
- Framework: Django (REST-based)
- Database: PostgreSQL
- Containerization: Docker & Docker Compose
- CI: GitHub Actions

## Repository Structure

```text
pharmacio-backend/
├── config/            # Django project configuration (settings, URLs, WSGI/ASGI)
├── users/             # User management (extends Django auth)
├── rbac/              # Role-Based Access Control logic
├── files/             # File upload handling & metadata
├── ai_integration/    # AI / OCR engine integration
├── inventory/         # Inventory & stock management
├── sales/             # Sales history & demand tracking
├── capital/           # Financial / capital tracking
├── purchases/         # Purchase proposals & approval workflow
├── notifications/     # Notification system & alerting
├── manage.py          # Django CLI entrypoint
├── requirements.txt   # Python dependencies
├── Dockerfile         # Container image definition
├── docker-compose.yml # Local dev stack (DB, Redis, worker, backend)
└── .env.example       # Example environment variables (no secrets)
```

---

## Getting Started

Quick, 3-step setup for new developers (Docker recommended):

### Prerequisites

- Docker & Docker Compose
- Python 3.10+ (for local venv workflows)
- Git
- (Optional) WSL2 on Windows for best Docker/CLI experience

### 1) Clone the repo

```bash
git clone <repo-url>
cd pharmacio-backend
```

### 2) Environment

Copy the example env file and adjust if needed:

Windows:

```bash
Copy-Item .env.example .env
```

Or (cross-platform):

```bash
cp .env.example .env
```

At minimum set `DATABASE_URL` and `SECRET_KEY` when running outside Docker.

### 3) Run (Docker)

```bash
docker compose up --build -d
```

- The stack includes the Django backend, PostgreSQL and Redis by default.
- Default backend URL: `http://localhost:8000` (health: `/health/`).

Run migrations and create an admin user (replace `<service>` with `backend` or `web` depending on your compose file):

```bash
docker compose exec <service> python manage.py migrate
docker compose exec <service> python manage.py createsuperuser
```

### Useful commands

| Command                               | Purpose                    |
| ------------------------------------- | -------------------------- |
| `python manage.py migrate`            | Apply DB migrations        |
| `python manage.py createsuperuser`    | Create admin user          |
| `python manage.py loaddata <fixture>` | Load fixture data          |
| `docker compose logs -f`              | Follow service logs        |
| `docker compose down`                 | Stop and remove containers |

### Troubleshooting & tips

- If DB connection fails, start only the DB: `docker compose up -d postgres` or ensure local Postgres is running.
- If unsure which service name to use for `docker compose exec`, run `docker compose ps` to check service names.
- Prefer WSL2 on Windows for best compatibility with Docker and development tools.
