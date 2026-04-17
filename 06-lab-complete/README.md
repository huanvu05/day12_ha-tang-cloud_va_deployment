# Day 12 Final Project

Production-ready FastAPI AI agent with Redis-backed conversation history, API key authentication, per-user rate limiting, monthly cost guard, health/readiness probes, graceful shutdown, and deployment manifests for Render/Railway.

## Project Layout

```text
06-lab-complete/
├── app/
│   ├── auth.py
│   ├── config.py
│   ├── cost_guard.py
│   ├── main.py
│   └── rate_limiter.py
├── utils/mock_llm.py
├── Dockerfile
├── docker-compose.yml
├── render.yaml
├── railway.toml
├── .env.example
├── .gitignore
└── check_production_ready.py
```

## Run Locally

```bash
cp .env.example .env.local
docker compose up --build
```

## Smoke Test

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready

API_KEY=$(grep AGENT_API_KEY .env.local | cut -d= -f2)

curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo","question":"My name is Alice"}'

curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo","question":"What is my name?"}'
```

## Deployment

`render.yaml` provisions both the web service and Redis. `railway.toml` is included for Railway, but Railway still needs a Redis service attached and `REDIS_URL` configured in the dashboard or CLI.

## Verification

```bash
python check_production_ready.py
```
