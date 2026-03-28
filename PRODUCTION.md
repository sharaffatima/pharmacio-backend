# Production Checklist

Before deploying to production, go through every item below. Each one is **required** unless marked optional.

## 1. Secrets & Environment

- [ ] Generate a strong, unique `DJANGO_SECRET_KEY` (e.g. `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- [ ] Set `DJANGO_DEBUG=False` — **never** run with debug on in production
- [ ] Set `DJANGO_ALLOWED_HOSTS` to your actual domain(s) (e.g. `api.pharmacio.example.com`)
- [ ] Use strong, unique passwords for `DB_PASSWORD`, `MINIO_ROOT_PASSWORD`
- [ ] Set a strong, random `INTERNAL_SERVICE_TOKEN` for OCR callback authentication
- [ ] Set a strong `AI_ENGINE_API_KEY` for outbound AI engine calls
- [ ] Store all secrets in a vault or secret manager — **never** commit `.env` to git

## 2. Django Security Settings

These settings need to be added or changed in `config/settings.py` for production:

```python
# Re-enable CSRF middleware (currently commented out)
MIDDLEWARE = [
    ...
    'django.middleware.csrf.CsrfViewMiddleware',   # uncomment this line
    ...
]

# HTTPS / cookie hardening
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000          # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

## 3. Web Server

- [ ] **Do not use `runserver` in production** — it is single-threaded and not designed for production traffic
- [ ] Use **Gunicorn** (or uWSGI) as the WSGI server:
  ```bash
  pip install gunicorn
  gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
  ```
- [ ] Put a **reverse proxy** (Nginx, Caddy, or a cloud LB) in front of Gunicorn for TLS termination, static files, and rate limiting
- [ ] Update the `Dockerfile` CMD and `docker-compose.yml` command to use Gunicorn instead of `runserver`

## 4. Database

- [ ] Use a managed PostgreSQL instance or a hardened self-hosted setup
- [ ] Do **not** expose port `5432` to the public — remove the `ports:` mapping in compose or bind to `127.0.0.1`
- [ ] Enable SSL connections between Django and Postgres
- [ ] Set up automated backups and test restores

## 5. Redis

- [ ] Set a Redis password (`requirepass`) and update `CELERY_BROKER_URL` / `REDIS_URL` accordingly
- [ ] Do **not** expose port `6379` publicly
- [ ] (Optional) Enable Redis persistence if you need durable task queues

## 6. File Storage

- [ ] Use a real S3 bucket or production MinIO cluster (`FILE_STORAGE_BACKEND=s3`)
- [ ] Set proper bucket policies — no public access unless intentional
- [ ] Enable server-side encryption on the bucket
- [ ] Remove the MinIO dev container from your production compose file

## 7. Docker & Deployment

- [ ] Use a pinned image tag (e.g. `python:3.11.9-slim`) instead of `python:3.11-slim`
- [ ] Run containers as non-root (already configured in the Dockerfile)
- [ ] Remove the `volumes: - .:/app` bind mount — it is for dev-time hot-reload only
- [ ] Do **not** run `migrate` in the container start command — run it once as a deploy step instead
- [ ] Set `restart: always` (instead of `unless-stopped`) in production compose
- [ ] Use Docker secrets or an external vault instead of `.env` files

## 8. Logging & Monitoring

- [ ] Configure structured JSON logging (e.g. `python-json-logger`)
- [ ] Ship logs to a central system (ELK, Loki, CloudWatch, etc.)
- [ ] Set up uptime monitoring on `/health/` and `/health/db/`
- [ ] Set up alerting for Celery worker health (e.g. Flower, Prometheus exporter)

## 9. Rate Limiting & Auth

- [ ] Review the throttle rates in `settings.py` (`login: 5/min`, `register: 3/min`) and adjust for expected traffic
- [ ] Shorten JWT token lifetimes — the current `ACCESS_TOKEN_LIFETIME` of 24 hours is very long for production; consider 15–60 minutes
- [ ] Ensure the `token_blacklist` app is migrated (`python manage.py migrate`) so logout actually blacklists tokens

## 10. CI/CD

- [ ] Run `python manage.py test` in CI before every deploy
- [ ] Run `python manage.py check --deploy` — Django's built-in deployment checklist
- [ ] Pin all dependency versions in `requirements.txt` (no unpinned ranges)
- [ ] (Optional) Add `bandit` or `safety` to CI for security scanning
