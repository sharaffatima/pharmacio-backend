.PHONY: help migrate makemigrations shell test run createsuperuser clean seed-inventory logs down up build

help:
	@echo "Available commands:"
	@echo "  make migrate            - Run database migrations"
	@echo "  make makemigrations     - Create new migrations"
	@echo "  make shell              - Open Django shell"
	@echo "  make test               - Run all tests"
	@echo "  make test-ai            - Run ai_integration tests only"
	@echo "  make run                - Start development server (local venv)"
	@echo "  make createsuperuser    - Create admin user"
	@echo "  make seed-inventory     - Load seed data for inventory"
	@echo "  make clean              - Remove __pycache__ and .pyc files"
	@echo "  make logs               - Follow container logs (Docker)"
	@echo "  make up                 - Start Docker containers"
	@echo "  make down               - Stop Docker containers"
	@echo "  make build              - Rebuild Docker images"

# Database commands
migrate:
	docker compose exec backend python manage.py migrate

makemigrations:
	docker compose exec backend python manage.py makemigrations

# Django shell
shell:
	docker compose exec backend python manage.py shell

# Testing
test:
	docker compose exec backend python manage.py test -v 2

test-ai:
	docker compose exec backend python manage.py test ai_integration -v 2


# Server
run:
	pipenv run python manage.py runserver

# Admin
createsuperuser:
	docker compose exec backend python manage.py createsuperuser

# Seed data
seed-inventory:
	docker compose exec backend python manage.py loaddata inventory.seed

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Docker Compose
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

build:
	docker compose build

logs:
	docker compose logs -f
