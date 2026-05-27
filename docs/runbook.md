# Ops Runbook

Operational playbook for a self-hosted Tawiza instance running on Docker
Compose (the canonical deployment described in
[`self-hosting.md`](self-hosting.md)). This document covers the deploy
flow, rollback, where logs live, common incidents, and how to verify a
deploy.

> Scope: production-style single-host Docker Compose deployment. Adapt
> commands for your orchestrator (Kubernetes, Nomad, etc.) when you run
> something else.

---

## 1. Deploy

The canonical deploy is: pull the new code, rebuild the images, restart
the stack, run pending database migrations.

### 1.1 Pre-flight

Before deploying:

- Confirm you are on the host that owns the running stack:
  `docker compose ps` should list `tawiza-postgres`, `tawiza-redis`,
  and the app containers.
- Confirm `.env` is present and contains the production secrets
  (`DATABASE_PASSWORD`, `REDIS_PASSWORD`, `GRAFANA_PASSWORD`, `SECRET_KEY`).
  `docker compose config` fails fast if any required value is missing.
- Take a database snapshot (see [Sauvegardes in self-hosting.md](self-hosting.md#sauvegardes)):
  ```bash
  docker compose exec postgres pg_dump -U tawiza tawiza > backup_$(date +%Y%m%d_%H%M).sql
  ```
- Note the current image digests so you can roll back:
  ```bash
  docker compose images > /tmp/images_before_$(date +%Y%m%d_%H%M).txt
  ```

### 1.2 Canonical deploy flow

From the repo root on the host:

```bash
cd tawiza

# 1. Pull the new code.
git fetch --tags
git checkout main
git pull --ff-only origin main

# 2. Rebuild the images that changed and recreate containers.
docker compose pull         # pulls postgres/redis/prometheus/grafana
docker compose build        # rebuilds backend/frontend if they have Dockerfiles
docker compose up -d        # recreates only the containers whose config changed

# 3. Apply database migrations.
docker compose exec backend alembic upgrade head
```

`docker compose up -d` is idempotent and only restarts services whose
image or config changed. If you need to force a clean restart of a
specific service:

```bash
docker compose up -d --force-recreate --no-deps backend
```

### 1.3 Alembic migrations

Migrations live in [`alembic/versions/`](../alembic/versions). Order
matters:

1. **Always run `alembic upgrade head` after `docker compose up -d`**,
   not before. The backend container needs to start first because that
   is where the alembic CLI lives.
2. New columns/tables created by a migration must be backward-compatible
   with the *previous* code version for a few seconds during rollout
   (the old container is still serving requests while the new one starts).
   If a migration drops or renames a column, deploy in two steps: ship
   the code that no longer reads it, *then* ship the migration.
3. Migration history can be inspected with:
   ```bash
   docker compose exec backend alembic current
   docker compose exec backend alembic history --verbose
   ```
4. If `alembic upgrade head` fails mid-way, **do not** retry blindly.
   Capture the error, see [Common incidents](#4-common-incidents) §4.1,
   and decide whether to roll back the code or fix the migration forward.

### 1.4 Frontend-only or backend-only deploy

When the change only touches one service, restart only that one to keep
the rest warm:

```bash
docker compose up -d --build backend     # backend code changes
docker compose up -d --build frontend    # frontend changes
```

---

## 2. Rollback

A rollback is a deploy in reverse. There are two flavours: revert the
code (fast, safe when no destructive migration ran) and revert the
database (only when a migration corrupted data).

### 2.1 Decide which rollback you need

| Symptom | Action |
|---------|--------|
| New build is unhealthy, no migrations ran | Roll back code only (§2.2) |
| New build is unhealthy, migration ran and is reversible | Roll back code, then `alembic downgrade -1` (§2.3) |
| Migration corrupted data | Restore from pre-deploy `pg_dump` (§2.4) |

### 2.2 Roll back the code

Pin to the previous commit (or the previous tag) and redeploy:

```bash
# Find the commit you were on before the deploy.
git reflog                       # or check /tmp/images_before_*.txt
git checkout <previous-sha-or-tag>

docker compose build
docker compose up -d
```

If you tag releases (`v1.2.3`), pin to the previous tag instead:

```bash
git checkout v1.2.2
docker compose build
docker compose up -d
```

If the images are tagged in a registry, you can also pin by image tag in
`docker-compose.yml` (e.g. `image: tawiza/backend:v1.2.2`) and run
`docker compose up -d` without rebuilding.

### 2.3 Roll back a migration

Only when the migration is reversible (has a `downgrade()` body that
matches `upgrade()`):

```bash
docker compose exec backend alembic downgrade -1
```

Verify with `alembic current` that you are now on the expected revision.
If `downgrade()` is a `pass` (irreversible migration), you must restore
from the snapshot instead.

### 2.4 Restore from snapshot

Destructive, last resort. Stops writes to the database for the duration
of the restore.

```bash
docker compose stop backend frontend
cat backup_YYYYMMDD_HHMM.sql | docker compose exec -T postgres psql -U tawiza tawiza
docker compose start backend frontend
```

After restore, verify with [§5 Verifying a deploy](#5-verifying-a-deploy).

---

## 3. Logs

Tawiza does not centralise logs by default; every container writes to
stdout/stderr and Docker captures it. Tail the right one depending on
what you are debugging.

### 3.1 Per-service quick tail

```bash
# Everything, last 50 lines, then follow.
docker compose logs -f --tail=50

# A specific service.
docker compose logs -f --tail=200 backend
docker compose logs -f --tail=200 frontend
docker compose logs -f --tail=200 postgres
docker compose logs -f --tail=200 redis
```

### 3.2 What each service writes

| Service | Container | What you'll find |
|---------|-----------|------------------|
| Backend (FastAPI) | `tawiza-backend` | Request logs, Loguru-formatted app logs, alembic output when migrations run |
| Frontend (Next.js) | `tawiza-frontend` | Build output, SSR errors, fetch failures from the browser |
| PostgreSQL | `tawiza-postgres` | Connection errors, slow queries (if enabled), `FATAL`/`PANIC` lines |
| Redis | `tawiza-redis` | Auth failures, OOM evictions, `replicaof` events |
| Prometheus | `tawiza-prometheus` | Scrape failures (= a service is down or `/metrics` is broken) |
| Grafana | `tawiza-grafana` | Login failures, plugin load errors |

### 3.3 Filesystem locations

Logs are stored by the Docker daemon under
`/var/lib/docker/containers/<container-id>/<container-id>-json.log` on
the host. Rotate them with the Docker daemon's `log-opts`
(`max-size`, `max-file`) in `/etc/docker/daemon.json` — otherwise a
chatty container will fill the disk (see §4.4).

If you ship logs to Loki, Datadog, or a syslog endpoint, configure the
`logging:` driver per service in `docker-compose.override.yml` rather
than editing `docker-compose.yml` itself.

### 3.4 Useful grep patterns

```bash
# Errors from the backend in the last hour.
docker compose logs --since=1h backend | grep -Ei 'error|exception|traceback'

# 5xx responses.
docker compose logs --since=1h backend | grep -E ' (5[0-9]{2}) '

# Database connection failures.
docker compose logs --since=1h backend | grep -i 'asyncpg\|connection refused\|could not connect'
```

---

## 4. Common incidents

One section per incident type. Each has a symptom, a diagnostic command,
and the fix. Run the diagnostic first — don't restart things blindly.

### 4.1 Alembic migration fails mid-way

**Symptom**: `docker compose exec backend alembic upgrade head` exits
non-zero, often with `sqlalchemy.exc.OperationalError` or a Python
traceback.

**Diagnose**:
```bash
docker compose exec backend alembic current
docker compose exec backend alembic history --verbose | head -30
docker compose logs --tail=200 backend | grep -i alembic
```

**Fix**:
- If the failure is transient (network blip, lock timeout), retry:
  `docker compose exec backend alembic upgrade head`.
- If a partial DDL change was applied (PostgreSQL DDL is transactional
  per statement, but multiple statements in one revision can leave the
  schema half-migrated), inspect the schema with
  `docker compose exec postgres psql -U tawiza -c '\d <table>'` and
  decide whether to:
  - Patch the migration's `upgrade()` to be idempotent
    (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`) and rerun.
  - `alembic downgrade -1` then ship a fixed migration.
- If neither works: restore from snapshot (§2.4).

### 4.2 Database connection lost

**Symptom**: backend returns 503, logs show
`asyncpg.exceptions.ConnectionDoesNotExistError` or
`could not connect to server`.

**Diagnose**:
```bash
docker compose ps postgres
docker compose exec postgres pg_isready -U tawiza
docker compose logs --tail=100 postgres
```

**Fix**:
- If `postgres` is `unhealthy` / restarting: check disk space first
  (§4.4). PostgreSQL refuses to start when the data volume is full.
- If `postgres` is healthy but the backend still can't connect: the
  backend container probably has a stale connection pool. Restart it:
  `docker compose restart backend`.
- If `pg_isready` shows `accepting connections` but app login fails:
  re-check `DATABASE_URL` in `.env` against the credentials in
  `POSTGRES_USER`/`POSTGRES_PASSWORD`. They must match.

### 4.3 Ollama is down (LLM unreachable)

**Symptom**: TAJINE/agent responses fail; backend logs show
`httpx.ConnectError` to `http://localhost:11434` or
`http://ollama:11434`. `/api/v1/health/detailed` reports
`ollama: disconnected`.

**Diagnose**:
```bash
# If Ollama runs on the host (default install):
systemctl status ollama
curl -sf http://localhost:11434/api/tags

# If Ollama runs in a container:
docker ps --filter name=ollama
docker logs --tail=100 ollama
```

**Fix**:
- Restart Ollama: `systemctl restart ollama` (host) or
  `docker restart ollama` (container).
- Confirm `OLLAMA_URL` in `.env` points to a reachable address. From
  inside the backend container, `localhost` is the container itself —
  use `host.docker.internal` (Docker Desktop) or the host's LAN IP / a
  named service.
- If Ollama is down for an extended outage, the system falls back to
  Groq → OpenRouter per the cascade documented in the README. Confirm
  `GROQ_API_KEY` / `OPENROUTER_API_KEY` are set if you want the
  fallback to actually trigger.

### 4.4 Disk full

**Symptom**: random `IOError`, PostgreSQL refuses writes, Docker logs
say `no space left on device`.

**Diagnose**:
```bash
df -h /
docker system df
du -sh /var/lib/docker/containers/* 2>/dev/null | sort -h | tail
du -sh /var/lib/docker/volumes/* 2>/dev/null | sort -h | tail
```

**Fix**:
- Prune dangling images and stopped containers (safe):
  ```bash
  docker system prune -f
  ```
- Truncate runaway container logs (safe, but log history is lost):
  ```bash
  truncate -s 0 /var/lib/docker/containers/<id>/<id>-json.log
  ```
  Permanent fix: set `log-opts` in `/etc/docker/daemon.json` and restart
  the Docker daemon.
- If the Postgres volume is the culprit, archive and drop old
  large tables before extending the disk; do not delete files under
  `postgres_data/` directly.

### 4.5 Redis evicting / authentication failures

**Symptom**: backend logs show `NOAUTH Authentication required.` or
`OOM command not allowed when used memory > 'maxmemory'`.

**Diagnose**:
```bash
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" PING
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" INFO memory
```

**Fix**:
- `NOAUTH`: re-check `REDIS_PASSWORD` in `.env` matches what the
  backend uses. Restart backend after fixing.
- OOM: either raise `maxmemory` for the Redis container or set a
  proper eviction policy (`maxmemory-policy allkeys-lru`). Cache misses
  are recoverable; data loss only matters if you've used Redis as a
  queue persistence layer.

### 4.6 Backend healthcheck flapping (degraded)

**Symptom**: `/health/ready` returns 503 intermittently; Prometheus
shows scrape failures.

**Diagnose**:
```bash
curl -sf http://localhost:8000/health/full | jq
curl -sf http://localhost:8000/api/v1/health/detailed | jq
docker compose logs --tail=200 backend | grep -Ei 'warn|error'
```

The `/health/full` endpoint reports per-dependency status (database,
Ollama, Redis, disk, memory) — start with the one showing `down` or
`degraded`.

---

## 5. Verifying a deploy

Run these checks after every deploy. If any fail, treat it as a deploy
failure and roll back per §2.

### 5.1 Container state

```bash
docker compose ps
```

Every service must be `Up` and (where a healthcheck is defined,
e.g. `postgres`, `redis`) `healthy`.

### 5.2 Healthcheck endpoints

Tawiza exposes several health endpoints on the backend (port 8000):

| Endpoint | What it tells you |
|----------|-------------------|
| `GET /health/live` | The process is alive (cheap; used by k8s liveness probes) |
| `GET /health/ready` | Critical deps are up (database + Ollama). Returns 503 if not |
| `GET /health/startup` | Startup finished |
| `GET /health/full` | Per-dependency status: database, Ollama, Redis, disk, memory |
| `GET /health/sources` | External data-source APIs (SIRENE, DVF, BAN, France Travail, OFGL) |
| `GET /api/v1/health/detailed` | Backend, Ollama, Neo4j, Postgres, WebSocket, scheduler, telemetry |
| `GET /metrics` | Prometheus metrics (used by the bundled Prometheus container) |

Smoke them after deploy:

```bash
curl -sf http://localhost:8000/health/live  | jq .status   # expect "healthy"
curl -sf http://localhost:8000/health/ready | jq .status   # expect "healthy"
curl -sf http://localhost:8000/health/full  | jq '.status, .dependencies[].name + ":" + .dependencies[].status'
curl -sf http://localhost:8000/api/v1/health/detailed | jq '.overall'
```

### 5.3 Frontend smoke

```bash
curl -sI http://localhost:3000/ | head -1     # expect HTTP/1.1 200
```

Then in a browser, spot-check that these pages render without console
errors:

- `/` — landing
- `/dashboard` — main dashboard
- `/sources` — data-source catalog (reads `/health/sources`)
- `/tajine` — TAJINE agent (exercises the LLM cascade)

### 5.4 Migration sanity

```bash
docker compose exec backend alembic current
```

The output should match the head of `alembic/versions/`. If it lags by
one or more revisions, finish the upgrade before declaring the deploy
done.

### 5.5 Metrics / dashboards

If Prometheus + Grafana are enabled (`docker compose up -d prometheus
grafana`), open:

- Prometheus: `http://localhost:9090/targets` — every target must be
  `UP`.
- Grafana: `http://localhost:3003/` — the bundled dashboards under
  *Provisioning → Dashboards* should be populated within ~1 minute of
  the deploy.

If a target stays `DOWN` for more than two scrape intervals after the
deploy, treat it as a regression.
