# AAS (Asset Administration Shell) Data Source

Adapter that connects to an AAS-compatible viewer API (e.g. TwinSphere) and
exposes shells and submodels through the i3X interface.

## Mapping

| AAS Concept | i3X Concept |
|-------------|-------------|
| Shell | Root object instance (`aas-shell-type`) |
| Submodel | Child object instance (`aas-submodel-type`) |
| Shell contains Submodel | `HasComponent` / `ComponentOf` relationships |

## Element ID Scheme

IDs are constructed from base64-encoded AAS identifiers:

- Shell: `aas:<base64(aasId)>`
- Submodel: `aas:<base64(aasId)>:<base64(submodelId)>`

The AAS API requires base64-encoded IDs in path parameters for follow-up calls.

## Configuration

```json
{
    "type": "aas",
    "config": {
        "base_url": "https://viewer.demo.cloud.twinsphere.io"
    }
}
```

| Key | Required | Description |
|-----|----------|-------------|
| `base_url` | Yes | Base URL of the AAS viewer API |

## Behavior

- **On startup**, the adapter fetches all shells via `/api/ShellList` (with cursor
  pagination) and their submodel references via `/api/submodels/{aasId}`.
- **Submodel values** are fetched lazily on first access via
  `/api/submodels/{aasId}/submodel/{submodelId}` and cached.
- **Read-only**: update requests return a failure response since the upstream
  API is a viewer service.
- **Subscriptions**: no background updater thread. Subscription support requires
  adding a polling mechanism in a future iteration.

## Supported i3X Endpoints

| Endpoint | Supported |
|----------|-----------|
| `GET /namespaces` | Yes |
| `GET /objecttypes` | Yes |
| `POST /objecttypes/query` | Yes |
| `GET /relationshiptypes` | Yes |
| `POST /relationshiptypes/query` | Yes |
| `GET /objects` | Yes (with type filter and root filter) |
| `POST /objects/list` | Yes |
| `POST /objects/related` | Yes |
| `POST /objects/value` | Yes (with maxDepth recursion) |
| `POST /objects/history` | No (no historical data in AAS viewer) |
| `PUT /objects/{id}/value` | No (read-only) |
| Subscriptions | No (no live updates from source) |

## Running Tests

From the `demo/server` directory:

```bash
python -m pytest data_sources/aas/test_aas_data_source.py -v
```

Tests use mocked HTTP responses and require no network access.
