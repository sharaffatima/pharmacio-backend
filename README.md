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

pharmacio-backend/
│
├── config/ # Django project configuration
│ ├── settings.py # Global settings (DB, apps, env vars)
│ ├── urls.py # Root URL configuration
│ ├── asgi.py # ASGI entrypoint
│ └── wsgi.py # WSGI entrypoint
│
├── users/ # User management (extends Django auth)
├── rbac/ # Role-Based Access Control logic
├── files/ # File upload handling & metadata
├── ai_integration/ # AI/OCR communication layer
├── inventory/ # Inventory domain (stock management)
├── sales/ # Sales history & demand tracking
├── capital/ # Financial tracking (capital changes)
├── purchases/ # Purchase proposals & approval workflow
├── notifications/ # Notification system & alert logging
│
├── manage.py # Django management CLI
├── requirements.txt # Python dependencies
├── Dockerfile # Backend container definition
├── docker-compose.yml # Local dev stack (backend + DB + Redis)
├── .env.example # Example environment variables (no secrets)

## Getting Started

1. Clone Repository
   `git clone <repo-url>`
   `cd pharmacio-backend`

2. Environment variables
   Copy the example file:
   `Copy-Item .env.example .env` (Windows)
   Open .env and adjust values if needed (defaults should work for local dev).

3. Run with Docker
   `docker compose up --build`
   or `docker compose up --build -d` to run in the background
   Thi starts Django backend, PostgreSQL databse and Redis

4. Verify it works
   http://localhost:8000/health/

You can view the logs with
`docker compose logs -f backend`

Or Stop the services with
`docker compose down`
