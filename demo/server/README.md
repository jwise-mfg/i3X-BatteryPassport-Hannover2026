# i3X API Server — AAS Adapter

FastAPI server implementing the i3X (Industrial Information Interface eXchange) API, backed by an Asset Administration Shell viewer data source.

## Structure

- **app.py** — Main FastAPI application with startup/shutdown lifecycle
- **models.py** — Pydantic models for all i3X data structures
- **routers/** — API endpoint handlers
  - `info.py` — Server info and capabilities (`GET /info`)
  - `namespaces.py` — Namespace listing (`GET /namespaces`)
  - `typeDefinitions.py` — Object type and relationship type queries
  - `objects.py` — Object exploration, value queries, and updates
  - `subscriptions.py` — Subscription lifecycle and streaming
  - `utils.py` — Shared response formatting helpers
- **data_sources/** — Data source abstraction
  - `data_interface.py` — Abstract `I3XDataSource` interface
  - `factory.py` — Factory for creating data sources from config
  - `aas/` — AAS adapter (see [aas/README.md](data_sources/aas/README.md))

## Setup

```bash
# Use the setup script (creates venv, installs deps, starts server)
./setup.sh

# Or manually
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config-aas.json config.json
python app.py
```

## Docker

```bash
cp config-aas.json config.json
docker build -t i3x-aas-demo .
docker run --rm -p 8081:8081 i3x-aas-demo
```

## Configuration

Copy `config-aas.json` to `config.json` and adjust as needed. Key fields:

| Field | Default | Description |
|-------|---------|-------------|
| `port` | 8081 | Server listen port |
| `host` | 0.0.0.0 | Bind address |
| `debug` | true | Enable auto-reload |
| `app.root_path` | /v1 | URL prefix for all endpoints |
| `data_source.type` | aas | Data source type |
| `data_source.config.base_url` | (required) | AAS viewer API URL |

## API Endpoints

All endpoints are prefixed with the configured `root_path` (e.g. `/v1`).

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/info` | Server info and capabilities |
| GET | `/namespaces` | List namespaces |
| GET | `/objecttypes` | List object types |
| POST | `/objecttypes/query` | Query object types by ID |
| GET | `/relationshiptypes` | List relationship types |
| POST | `/relationshiptypes/query` | Query relationship types by ID |
| GET | `/objects` | List object instances |
| POST | `/objects/list` | Get objects by ID |
| POST | `/objects/related` | Get related objects |
| POST | `/objects/value` | Get current values |
| POST | `/objects/history` | Get historical values |

Interactive documentation is available at `/docs` (Swagger) and `/redoc`.

## Tests

```bash
# AAS adapter unit tests (no network)
python -m pytest data_sources/aas/test_aas_data_source.py -v

# Integration tests (requires network for AAS API)
python -m pytest test_app.py -v
```
