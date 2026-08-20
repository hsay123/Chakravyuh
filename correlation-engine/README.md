# Correlation Engine — TrapNet-CRS

Sits between honeypots (DataTrap / Q-Cowrie) and the Buttercup CRS. Consumes structured attack events from Redis, matches them against a configurable asset registry, classifies the technique, and triggers Buttercup fuzz/patch tasks when the technique aligns with watched vulnerability classes.

## Architecture

```
Honeypots ──▶ Redis stream (honeypot_events)
                   │
          Correlation Engine
          ├─ asset lookup (YAML config)
          ├─ technique classification
          ├─ Buttercup task submission (mock-competition-api)
          └─ status publish → Backend Orchestrator
```

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `EVENT_STREAM` | `honeypot_events` | Stream key to consume |
| `POLL_INTERVAL` | `1.0` | Seconds to block on XREADGROUP |
| `BUTTERCUP_API_URL` | `http://mock-competition-api:8080` | Mock competition API |
| `ORCHESTRATOR_URL` | `http://backend-orchestrator:8000` | Backend orchestrator |
| `ASSETS_PATH` | `config/assets.yaml` | Asset registry path |

## Asset Registry

Edit `config/assets.yaml` to add/remove decoys. Never hardcode mappings in code.

## Run locally

```bash
pip install -r requirements.txt
python -m app.main
```

## Docker

```bash
docker build -t trapnet-correlation-engine .
docker run -e REDIS_URL=redis://host.docker.internal:6379/0 trapnet-correlation-engine
```

## Health Check

```
GET :8100/healthz
```
