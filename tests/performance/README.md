# ChronoLegal — Performance Tests

Locust-based load tests for the ChronoLegal API.

## Prerequisites

```bash
pip install locust
```

The stack must be running (`make dev`) with a seeded database and at least one Ollama model pulled.

## Create Load Test User

Before running tests, create the dedicated load-test user:

```bash
docker compose exec backend python -c "
import asyncio
from app.core.database import get_db
from app.services.legal.user_service import UserService
from app.schemas.user import UserCreate

async def create():
    async for db in get_db():
        svc = UserService(db)
        await svc.create_user(UserCreate(
            email='loadtest@chronolegal.test',
            password='LoadTest123!',
            full_name='Load Tester',
        ))

asyncio.run(create())
"
```

## Running Tests

### Full load suite (Locust web UI)
```bash
cd tests/performance
locust -f locustfile.py --host http://localhost:8000
# Open http://localhost:8089 — set users and start
```

### Headless CI run
```bash
locust -f locustfile.py --host http://localhost:8000 \
    --users 50 --spawn-rate 5 --run-time 60s --headless \
    --html reports/load_report.html \
    --csv reports/load_stats
```

### Search-only scenario
```bash
locust -f scenarios/search_load.py --host http://localhost:8000 \
    --users 50 --spawn-rate 5 --run-time 120s --headless
```

### Chat/RAG scenario (lower concurrency)
```bash
locust -f scenarios/chat_load.py --host http://localhost:8000 \
    --users 10 --spawn-rate 1 --run-time 120s --headless
```

## Target SLAs

| Endpoint | p50 | p95 | Error rate |
|----------|-----|-----|-----------|
| `POST /search/` | < 200ms | < 500ms | < 1% |
| `GET /search/suggestions` | < 50ms | < 100ms | < 1% |
| `POST /chat/` (non-streaming) | < 5s | < 15s | < 2% |
| `GET /analytics/dashboard` | < 300ms | < 800ms | < 1% |

## Reports

Reports are saved to `tests/performance/reports/` (gitignored).

```
reports/
├── load_report.html      # Human-readable Locust report
├── load_stats.csv        # Per-request aggregates
└── load_stats_history.csv # Time-series data
```
