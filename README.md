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

## Repository Strcucture

## Getting Started
