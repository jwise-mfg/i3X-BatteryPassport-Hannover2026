# i3X AAS Demo

A demonstration of the [i3X](https://www.i3x.dev) (Industrial Information Interface eXchange) API serving data from an [Asset Administration Shell](https://www.plattform-i40.de/IP/Navigation/EN/AssetAdministrationShell/assetadministrationshell.html) (AAS) backend. The server connects to a TwinSphere AAS viewer API, projects AAS Shells and Submodels into the i3X address space, and adds virtual demo objects to showcase cross-domain graph relationships.

## What It Does

The server exposes an i3X-compliant REST API backed by a live AAS data source. The demo model looks like this:

```
(root)
├── i3X Explained                          [folder]
│
├── Digital Passports                      [folder]
│   ├── DEMO-MB-EQS-BP-108-001234         [aas-shell]  ◄── HasDigitalPassport
│   │   ├── Nameplate                      [aas-submodel]
│   │   └── TechnicalData                  [aas-submodel]
│   ├── DEMO-RNO-ZOE-BP-052-00912         [aas-shell]
│   └── ... (100+ shells from TwinSphere)
│
└── Electric Vehicles                      [folder]
    ├── Mercedes EQS ──HasDigitalPassport──► (shell above)
    ├── Renault Zoe ───HasDigitalPassport──► ...
    ├── Fiat Grande Panda
    └── Toyota Urban Cruiser
```

- **AAS Shells** are fetched from the TwinSphere API at startup and exposed as i3X object instances
- **AAS Submodels** are exposed as components of their parent shell (HasComponent relationship)
- **Electric Vehicle** objects are virtual demo instances linked to specific AAS shells via a `HasDigitalPassport` / `DigitalPassportOf` graph relationship
- All standard i3X exploratory and query endpoints are supported (namespaces, types, objects, values, relationships)

## Quick Start

### Prerequisites

- Python 3.7+
- pip

### Setup

```bash
cd demo/server

# Option 1: Use the setup script (creates venv, installs deps, starts server)
chmod +x setup.sh
./setup.sh

# Option 2: Manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config-aas.json config.json
python app.py
```

On Windows, use `setup.ps1` or activate the venv with `.\venv\Scripts\Activate.ps1`.

The server starts on the port specified in `config.json` (default: 8081).

### Docker

```bash
cd demo/server
cp config-aas.json config.json
docker build -t i3x-aas-demo .
docker run --rm -p 8081:8081 i3x-aas-demo
```

### Verify It Works

- Swagger UI: http://localhost:8081/v1/docs
- Health check: http://localhost:8081/v1/info
- List objects: http://localhost:8081/v1/objects?root=true

## Configuration

The server reads `config.json` from the `demo/server/` directory. Copy `config-aas.json` as a starting point:

```json
{
    "port": 8081,
    "host": "0.0.0.0",
    "debug": true,
    "app": {
        "title": "API Beta",
        "description": "Industrial Information Interface eXchange API - 1.0 Beta",
        "version": "beta",
        "root_path": "/v1"
    },
    "data_source": {
        "type": "aas",
        "config": {
            "base_url": "https://viewer.demo.cloud.twinsphere.io"
        }
    },
    "capabilities": {
        "query": { "history": false },
        "update": false,
        "subscribe": false
    }
}
```

| Field | Description |
|-------|-------------|
| `port` | Server listen port |
| `app.root_path` | URL prefix for all endpoints (e.g. `/v1`) |
| `data_source.config.base_url` | TwinSphere (or AAS-compatible) viewer API URL |
| `capabilities` | Advertised server capabilities. This demo is read-only with no history or subscriptions. |

## Project Structure

```
demo/server/
├── app.py                  # FastAPI application entry point
├── models.py               # Pydantic request/response models
├── config-aas.json         # Example configuration
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container build
├── test_app.py             # Integration tests (FastAPI TestClient)
├── setup.sh / setup.ps1    # One-command setup scripts
├── static/                 # Swagger UI customization
├── routers/                # API endpoint handlers
│   ├── info.py             # GET /info
│   ├── namespaces.py       # GET /namespaces
│   ├── typeDefinitions.py  # Object type and relationship type endpoints
│   ├── objects.py          # Object explore, query, and update endpoints
│   ├── subscriptions.py    # Subscription endpoints
│   └── utils.py            # Shared response formatting helpers
└── data_sources/
    ├── data_interface.py   # Abstract I3XDataSource interface
    ├── factory.py          # Data source factory
    └── aas/                # AAS adapter
        ├── aas_data.py     # Static types, namespaces, virtual instances
        ├── aas_data_source.py  # I3XDataSource implementation
        ├── test_aas_data_source.py  # Unit tests (36 tests)
        └── README.md       # Adapter documentation
```

## Running Tests

```bash
cd demo/server
source venv/bin/activate

# AAS adapter unit tests (mocked HTTP, no network required)
python -m pytest data_sources/aas/test_aas_data_source.py -v

# Full integration tests (starts server, requires network for AAS API)
python -m pytest test_app.py -v
```

## Links

- [i3X specification](https://www.i3x.dev)
- [AAS specification](https://www.plattform-i40.de/IP/Navigation/EN/AssetAdministrationShell/assetadministrationshell.html)
- [TwinSphere](https://www.2-3.systems)
